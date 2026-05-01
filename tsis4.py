import pygame
import random
import psycopg2
import sys
import json
import os
from datetime import datetime

SCREEN_W = 800
SCREEN_H = 600
CELL = 20
GRID_W = SCREEN_W // CELL
GRID_H = SCREEN_H // CELL
PANEL = 200

BLACK = (0,0,0); WHITE = (255,255,255); RED = (255,0,0); GREEN = (0,255,0)
YELLOW = (255,255,0); PURPLE = (128,0,128); ORANGE = (255,165,0)
CYAN = (0,255,255); GRAY = (128,128,128); DARK_GRAY = (64,64,64)
DARK_RED = (139,0,0); BROWN = (139,69,19)

DB = {'host':'localhost','port':5432,'database':'snake_game','user':'postgres','password':'12345'}

class Database:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(**DB)
            self.cur = self.conn.cursor()
            self.cur.execute("CREATE TABLE IF NOT EXISTS players(id SERIAL PRIMARY KEY,username VARCHAR(50) UNIQUE)")
            self.cur.execute("CREATE TABLE IF NOT EXISTS sessions(id SERIAL,pid INTEGER REFERENCES players(id),score INTEGER,level INTEGER,played TIMESTAMP DEFAULT NOW())")
            self.conn.commit()
        except: self.conn = None
    
    def get_pid(self, name):
        if not self.conn: return None
        self.cur.execute("SELECT id FROM players WHERE username=%s",(name,))
        r = self.cur.fetchone()
        if r: return r[0]
        self.cur.execute("INSERT INTO players(username) VALUES(%s) RETURNING id",(name,))
        self.conn.commit()
        return self.cur.fetchone()[0]
    
    def save(self, name, score, lvl):
        if not self.conn: return
        pid = self.get_pid(name)
        self.cur.execute("INSERT INTO sessions(pid,score,level) VALUES(%s,%s,%s)",(pid,score,lvl))
        self.conn.commit()
    
    def top10(self):
        if not self.conn: return []
        self.cur.execute("SELECT p.username,s.score,s.level FROM sessions s JOIN players p ON s.pid=p.id ORDER BY score DESC LIMIT 10")
        return self.cur.fetchall()
    
    def best(self, name):
        if not self.conn: return 0
        pid = self.get_pid(name)
        self.cur.execute("SELECT MAX(score) FROM sessions WHERE pid=%s",(pid,))
        r = self.cur.fetchone()
        return r[0] if r and r[0] else 0

class Snake:
    def __init__(self):
        self.body = [(GRID_W//2, GRID_H//2)]
        self.dir = (1,0)
        self.grow = False
    
    def move(self):
        h = self.body[0]
        nh = (h[0]+self.dir[0], h[1]+self.dir[1])
        self.body.insert(0, nh)
        if not self.grow: self.body.pop()
        else: self.grow = False
    
    def ch_dir(self, d):
        if (d[0] != -self.dir[0] or d[1] != -self.dir[1]): self.dir = d
    
    def eat(self): self.grow = True
    
    def shorten(self):
        if len(self.body) > 2:
            self.body = self.body[:-2]
            return True
        return False
    
    def hit(self, obs):
        h = self.body[0]
        if h[0]<0 or h[0]>=GRID_W or h[1]<0 or h[1]>=GRID_H: return True
        if h in self.body[1:]: return True
        if h in obs: return True
        return False
    
    def draw(self, screen, color):
        for x,y in self.body:
            pygame.draw.rect(screen, color, (x*CELL, y*CELL, CELL-2, CELL-2))

class Food:
    def __init__(self, snake, obs, power):
        self.set(snake, obs, power)
    
    def set(self, snake, obs, power):
        occ = set(snake.body) | set(obs)
        if power: occ.add((power.x, power.y))
        free = [(x,y) for x in range(GRID_W) for y in range(GRID_H) if (x,y) not in occ]
        if not free: return
        x,y = random.choice(free)
        self.x, self.y = x, y
        r = random.random()
        if r < 0.1: self.type = 2
        elif r < 0.2: self.type = 1
        else: self.type = 0
        self.color = [RED, YELLOW, DARK_RED][self.type]
        self.points = [10, 50, -20][self.type]
        self.spawn = pygame.time.get_ticks() if self.type==1 else None
    
    def expired(self):
        return self.spawn and pygame.time.get_ticks() - self.spawn > 5000
    
    def draw(self, screen):
        pygame.draw.rect(screen, self.color, (self.x*CELL, self.y*CELL, CELL-2, CELL-2))

class Power:
    def __init__(self, snake, food, obs):
        self.set(snake, food, obs)
    
    def set(self, snake, food, obs):
        occ = set(snake.body) | set(obs)
        if food: occ.add((food.x, food.y))
        free = [(x,y) for x in range(GRID_W) for y in range(GRID_H) if (x,y) not in occ]
        if not free: self.active = False; return
        x,y = random.choice(free)
        self.x, self.y = x, y
        self.type = random.randint(0,2)
        self.color = [ORANGE, CYAN, PURPLE][self.type]
        self.active = True
        self.spawn = pygame.time.get_ticks()
    
    def expired(self):
        return pygame.time.get_ticks() - self.spawn > 8000
    
    def draw(self, screen):
        pygame.draw.rect(screen, self.color, (self.x*CELL, self.y*CELL, CELL-2, CELL-2))

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W+PANEL, SCREEN_H))
        pygame.display.set_caption("Snake Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Arial', 20)
        self.big = pygame.font.SysFont('Arial', 36)
        
        self.load_settings()
        
        self.db = Database()
        self.state = 0
        self.name = ""
        self.input = ""
        self.reset()
    
    def load_settings(self):
        """Загружает настройки из settings.json"""
        self.settings = {
            'snake_color': [0, 255, 0],
            'grid_overlay': True,
            'sound': True
        }
        
        if os.path.exists('settings.json'):
            try:
                with open('settings.json', 'r') as f:
                    loaded = json.load(f)
                    self.settings.update(loaded)
            except:
                pass
    
    def save_settings(self):
        """Сохраняет настройки в settings.json"""
        try:
            with open('settings.json', 'w') as f:
                json.dump(self.settings, f, indent=4)
        except:
            pass
    
    def reset(self):
        self.snake = Snake()
        self.score = 0
        self.lvl = 1
        self.eaten = 0
        self.obs = []
        self.power = None
        self.active = None
        self.shield = False
        self.end_time = 0
        self.base_spd = 10
        self.spd = 10
        self.delay = 1000 // self.spd
        self.last = 0
        self.spawn_timer = 0
        self.food = Food(self.snake, self.obs, self.power)
    
    def spawn_obs(self):
        if self.lvl < 3: return
        self.obs = []
        cnt = min(self.lvl-2, 10)
        head = self.snake.body[0]
        for _ in range(cnt):
            for _ in range(100):
                x,y = random.randint(0,GRID_W-1), random.randint(0,GRID_H-1)
                if (x,y) in self.snake.body: continue
                if abs(x-head[0])<=2 and abs(y-head[1])<=2: continue
                if (x,y) not in self.obs:
                    self.obs.append((x,y))
                    break
    
    def lvl_up(self):
        self.lvl += 1
        self.eaten = 0
        self.base_spd = 10 + (self.lvl-1)*2
        self.spd = self.base_spd
        self.delay = 1000 // self.spd
        self.spawn_obs()
    
    def apply_power(self):
        now = pygame.time.get_ticks()
        if self.power.type == 0:
            self.active = 0
            self.end_time = now + 5000
            self.spd = int(self.base_spd * 1.5)
        elif self.power.type == 1:
            self.active = 1
            self.end_time = now + 5000
            self.spd = max(5, int(self.base_spd * 0.7))
        else:
            self.shield = True
            self.active = 2
            self.end_time = now + 8000
        self.power.active = False
    
    def update(self):
        now = pygame.time.get_ticks()
        
        if now - self.last >= self.delay:
            self.last = now
            self.snake.move()
            head = self.snake.body[0]
            
            if self.snake.hit(self.obs):
                if self.shield:
                    self.shield = False
                    self.active = None
                    self.snake.body.pop(0)
                else:
                    self.db.save(self.name, self.score, self.lvl)
                    self.state = 2
                    return
            
            if head[0]==self.food.x and head[1]==self.food.y:
                self.score += self.food.points
                if self.food.type == 2:
                    if not self.snake.shorten():
                        self.db.save(self.name, self.score, self.lvl)
                        self.state = 2
                        return
                else:
                    self.snake.eat()
                    self.eaten += 1
                    if self.eaten >= 5:
                        self.lvl_up()
                self.food.set(self.snake, self.obs, self.power)
                self.delay = 1000 // self.spd
            
            if self.power and self.power.active and head[0]==self.power.x and head[1]==self.power.y:
                self.apply_power()
            
            if self.active and now > self.end_time:
                if self.active == 2: self.shield = False
                self.spd = self.base_spd
                self.active = None
        
        if not self.power or not self.power.active:
            self.spawn_timer += 1
            if self.spawn_timer > 300 and self.lvl >= 2:
                self.spawn_timer = 0
                self.power = Power(self.snake, self.food, self.obs)
        
        if self.food.expired():
            self.food.set(self.snake, self.obs, self.power)
        
        if self.power and self.power.active and self.power.expired():
            self.power.active = False
    
    def draw_grid(self):
        """Рисует сетку если включено в настройках"""
        if not self.settings['grid_overlay']:
            return
        
        for x in range(0, SCREEN_W, CELL):
            pygame.draw.line(self.screen, GRAY, (x, 0), (x, SCREEN_H), 1)
        for y in range(0, SCREEN_H, CELL):
            pygame.draw.line(self.screen, GRAY, (0, y), (SCREEN_W, y), 1)
    
    def draw(self):
        if self.state == 1:
            self.screen.fill(BLACK)
            self.draw_grid()
            
            for x,y in self.obs:
                pygame.draw.rect(self.screen, BROWN, (x*CELL, y*CELL, CELL-1, CELL-1))
            self.food.draw(self.screen)
            if self.power and self.power.active: self.power.draw(self.screen)
            self.snake.draw(self.screen, tuple(self.settings['snake_color']))
            
            pygame.draw.rect(self.screen, DARK_GRAY, (SCREEN_W,0,PANEL,SCREEN_H))
            txt = [f"Score: {self.score}", f"Level: {self.lvl}", f"Best: {self.db.best(self.name)}", f"Next: {self.eaten}/5"]
            if self.active == 0: txt.append("POWER: SPEED")
            elif self.active == 1: txt.append("POWER: SLOW")
            elif self.active == 2: txt.append("POWER: SHIELD")
            if self.shield: txt.append("SHIELD ACTIVE")
            for i,t in enumerate(txt):
                self.screen.blit(self.font.render(t,True,WHITE), (SCREEN_W+10, 50+i*30))
        
        elif self.state == 0:
            self.screen.fill(BLACK)
            t = self.big.render("SNAKE GAME", True, GREEN)
            self.screen.blit(t, t.get_rect(center=(SCREEN_W//2, 100)))
            if self.name:
                w = self.font.render(f"Welcome, {self.name}!", True, WHITE)
                self.screen.blit(w, w.get_rect(center=(SCREEN_W//2, 180)))
            
            btns = [("PLAY",230), ("TOP10",300), ("SETTINGS",370), ("NAME",440), ("QUIT",510)]
            mx,my = pygame.mouse.get_pos()
            for txt,y in btns:
                rect = self.font.render(txt, True, WHITE).get_rect(center=(SCREEN_W//2, y))
                col = YELLOW if rect.collidepoint(mx,my) else WHITE
                self.screen.blit(self.font.render(txt, True, col), rect)
        
        elif self.state == 2:
            o = pygame.Surface((SCREEN_W,SCREEN_H))
            o.set_alpha(200); o.fill(BLACK)
            self.screen.blit(o,(0,0))
            t = self.big.render("GAME OVER", True, RED)
            self.screen.blit(t, t.get_rect(center=(SCREEN_W//2,100)))
            self.screen.blit(self.font.render(f"Score: {self.score}",True,WHITE), self.font.render(f"Score: {self.score}",True,WHITE).get_rect(center=(SCREEN_W//2,200)))
            self.screen.blit(self.font.render("PLAY AGAIN",True,YELLOW), self.font.render("PLAY AGAIN",True,YELLOW).get_rect(center=(SCREEN_W//2,320)))
            self.screen.blit(self.font.render("MAIN MENU",True,YELLOW), self.font.render("MAIN MENU",True,YELLOW).get_rect(center=(SCREEN_W//2,390)))
        
        elif self.state == 3:
            self.screen.fill(BLACK)
            t = self.big.render("TOP 10", True, YELLOW)
            self.screen.blit(t, t.get_rect(center=(SCREEN_W//2,50)))
            top = self.db.top10()
            for i,row in enumerate(top[:10],1):
                y = 120 + i*35
                self.screen.blit(self.font.render(str(i),True,WHITE), (80, y))
                self.screen.blit(self.font.render(row[0][:12],True,WHITE), (150, y))
                self.screen.blit(self.font.render(str(row[1]),True,WHITE), (350, y))
                self.screen.blit(self.font.render(str(row[2]),True,WHITE), (500, y))
            b = self.font.render("BACK", True, YELLOW)
            self.back = b.get_rect(center=(SCREEN_W//2, SCREEN_H-50))
            self.screen.blit(b, self.back)
        
        elif self.state == 4:
            self.screen.fill(BLACK)
            t = self.big.render("ENTER NAME", True, GREEN)
            self.screen.blit(t, t.get_rect(center=(SCREEN_W//2,200)))
            r = pygame.Rect(SCREEN_W//2-150,300,300,50)
            pygame.draw.rect(self.screen, WHITE, r, 2)
            txt = self.font.render(self.input+"|", True, WHITE)
            self.screen.blit(txt, txt.get_rect(center=r.center))
        
        elif self.state == 5:
            self.screen.fill(BLACK)
            title = self.big.render("SETTINGS", True, YELLOW)
            self.screen.blit(title, title.get_rect(center=(SCREEN_W//2, 60)))
            
            y = 150
            grid_text = f"Grid: {'ON' if self.settings['grid_overlay'] else 'OFF'}"
            sound_text = f"Sound: {'ON' if self.settings['sound'] else 'OFF'}"
            
            grid_label = self.font.render(grid_text, True, WHITE)
            sound_label = self.font.render(sound_text, True, WHITE)
            color_label = self.font.render("Snake Color:", True, WHITE)
            
            self.screen.blit(grid_label, grid_label.get_rect(center=(SCREEN_W//2, y)))
            self.screen.blit(sound_label, sound_label.get_rect(center=(SCREEN_W//2, y+50)))
            self.screen.blit(color_label, color_label.get_rect(center=(SCREEN_W//2, y+100)))
            
            pygame.draw.rect(self.screen, tuple(self.settings['snake_color']), 
                           (SCREEN_W//2 + 100, y+85, 40, 30))
            
            save_btn = self.font.render("SAVE & BACK", True, GREEN)
            self.save_rect = save_btn.get_rect(center=(SCREEN_W//2, SCREEN_H-80))
            self.screen.blit(save_btn, self.save_rect)
            
            self.settings_buttons = {
                'grid': pygame.Rect(SCREEN_W//2 - 80, y-10, 160, 30),
                'sound': pygame.Rect(SCREEN_W//2 - 80, y+40, 160, 30),
                'color': pygame.Rect(SCREEN_W//2 - 80, y+90, 160, 30),
            }
        
        pygame.display.flip()
    
    def run(self):
        running = True
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT: running = False
                
                elif e.type == pygame.KEYDOWN:
                    if self.state == 1:
                        if e.key == pygame.K_UP: self.snake.ch_dir((0,-1))
                        elif e.key == pygame.K_DOWN: self.snake.ch_dir((0,1))
                        elif e.key == pygame.K_LEFT: self.snake.ch_dir((-1,0))
                        elif e.key == pygame.K_RIGHT: self.snake.ch_dir((1,0))
                        elif e.key == pygame.K_ESCAPE: self.state = 0
                    
                    elif self.state == 4:
                        if e.key == pygame.K_RETURN and self.input:
                            self.name = self.input
                            self.input = ""
                            self.state = 0
                        elif e.key == pygame.K_BACKSPACE:
                            self.input = self.input[:-1]
                        else:
                            self.input += e.unicode
                
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    if self.state == 0 and self.name:
                        mx,my = e.pos
                        play_rect = self.font.render("PLAY", True, WHITE).get_rect(center=(SCREEN_W//2, 230))
                        top10_rect = self.font.render("TOP10", True, WHITE).get_rect(center=(SCREEN_W//2, 300))
                        settings_rect = self.font.render("SETTINGS", True, WHITE).get_rect(center=(SCREEN_W//2, 370))
                        name_rect = self.font.render("NAME", True, WHITE).get_rect(center=(SCREEN_W//2, 440))
                        quit_rect = self.font.render("QUIT", True, WHITE).get_rect(center=(SCREEN_W//2, 510))
                        
                        if play_rect.collidepoint(mx,my):
                            self.reset()
                            self.state = 1
                        elif top10_rect.collidepoint(mx,my):
                            self.state = 3
                        elif settings_rect.collidepoint(mx,my):
                            self.state = 5
                        elif name_rect.collidepoint(mx,my):
                            self.input = ""
                            self.state = 4
                        elif quit_rect.collidepoint(mx,my):
                            running = False
                    
                    elif not self.name and self.state == 0:
                        self.state = 4
                    
                    elif self.state == 2:
                        mx,my = e.pos
                        again_rect = self.font.render("PLAY AGAIN", True, YELLOW).get_rect(center=(SCREEN_W//2, 320))
                        menu_rect = self.font.render("MAIN MENU", True, YELLOW).get_rect(center=(SCREEN_W//2, 390))
                        
                        if again_rect.collidepoint(mx,my):
                            self.reset()
                            self.state = 1
                        elif menu_rect.collidepoint(mx,my):
                            self.state = 0
                    
                    elif self.state == 3 and hasattr(self,'back') and self.back.collidepoint(e.pos):
                        self.state = 0
                    
                    elif self.state == 5:
                        if hasattr(self, 'settings_buttons'):
                            if self.settings_buttons['grid'].collidepoint(e.pos):
                                self.settings['grid_overlay'] = not self.settings['grid_overlay']
                            
                            elif self.settings_buttons['sound'].collidepoint(e.pos):
                                self.settings['sound'] = not self.settings['sound']
                            
                            elif self.settings_buttons['color'].collidepoint(e.pos):
                                colors = [(0,255,0), (255,0,0), (0,0,255), (255,255,0), (255,165,0), (255,0,255)]
                                current = tuple(self.settings['snake_color'])
                                if current in colors:
                                    idx = colors.index(current)
                                else:
                                    idx = 0
                                next_idx = (idx + 1) % len(colors)
                                self.settings['snake_color'] = list(colors[next_idx])
                            
                            elif hasattr(self, 'save_rect') and self.save_rect.collidepoint(e.pos):
                                self.save_settings()
                                self.state = 0
            
            if self.state == 1:
                self.update()
            
            self.draw()
            self.clock.tick(60)
        
        if self.db.conn:
            self.db.conn.close()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    Game().run()