import pygame
import random
import json
import os
from datetime import datetime
W, H = 800, 600
LANES = 3
LW = W // LANES
PW, PH = 60, 100
EW, EH = 55, 95

BLACK = (0,0,0); WHITE = (255,255,255); RED = (255,0,0); GREEN = (0,255,0)
BLUE = (0,0,255); YELLOW = (255,255,0); ORANGE = (255,165,0); CYAN = (0,255,255)
GRAY = (128,128,128); DARK = (64,64,64); BROWN = (139,69,19)

class Player:
    def __init__(self, color=BLUE):
        self.x = (W//2) - (PW//2)
        self.y = H - PH - 20
        self.rect = pygame.Rect(self.x, self.y, PW, PH)
        self.color = color
        self.lane = 1
        self.shield = False
        self.update()
    
    def update(self):
        self.rect.x = self.lane * LW + (LW - PW)//2
    
    def left(self):
        if self.lane > 0: self.lane -= 1; self.update()
    
    def right(self):
        if self.lane < LANES-1: self.lane += 1; self.update()
    
    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        if self.shield: pygame.draw.rect(screen, CYAN, self.rect, 3)

class Enemy:
    def __init__(self, lane, speed):
        x = lane * LW + (LW - EW)//2
        self.rect = pygame.Rect(x, -EH, EW, EH)
        self.speed = speed
    
    def update(self):
        self.rect.y += self.speed
        return self.rect.y > H
    
    def draw(self, screen):
        pygame.draw.rect(screen, RED, self.rect)

class Obstacle:
    def __init__(self, lane, speed):
        self.type = random.choice(['oil','pothole','barrier'])
        w = 40
        x = lane * LW + (LW - w)//2
        self.rect = pygame.Rect(x, -40, w, 40)
        self.color = BROWN if self.type == 'oil' else DARK
        self.speed = speed
    
    def update(self):
        self.rect.y += self.speed
        return self.rect.y > H
    
    def draw(self, screen):
        if self.type == 'oil':
            pygame.draw.circle(screen, self.color, self.rect.center, 20)
        else:
            pygame.draw.rect(screen, self.color, self.rect)

class Power:
    def __init__(self, lane, speed):
        self.type = random.choice([1,2,3])
        w = 30
        x = lane * LW + (LW - w)//2
        self.rect = pygame.Rect(x, -30, w, 30)
        self.color = [YELLOW, CYAN, GREEN][self.type-1]
        self.speed = speed
        self.spawn = pygame.time.get_ticks()
    
    def update(self):
        self.rect.y += self.speed
        return self.rect.y > H
    
    def expired(self):
        return pygame.time.get_ticks() - self.spawn > 8000
    
    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        pygame.draw.circle(screen, WHITE, self.rect.center, 5)

class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Racer Game")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Arial', 24)
        self.big = pygame.font.SysFont('Arial', 48)
        
        self.load_settings()
        self.load_scores()
        self.state = 0 
        self.name = ""
        self.name_active = True
        self.reset()
    
    def load_settings(self):
        self.settings = {'sound':True, 'color':BLUE, 'diff':'medium'}
        if os.path.exists('settings.json'):
            try:
                with open('settings.json','r') as f:
                    s = json.load(f)
                    if 'color' in s: s['color'] = tuple(s['color'])
                    self.settings.update(s)
            except: pass
    
    def save_settings(self):
        s = self.settings.copy()
        s['color'] = list(s['color'])
        with open('settings.json','w') as f:
            json.dump(s, f)
    
    def load_scores(self):
        self.scores = []
        if os.path.exists('scores.json'):
            try:
                with open('scores.json','r') as f:
                    self.scores = json.load(f)
                    self.scores.sort(key=lambda x:x['score'], reverse=True)
                    self.scores = self.scores[:10]
            except: pass
    
    def save_scores(self):
        with open('scores.json','w') as f:
            json.dump(self.scores[:10], f)
    
    def add_score(self):
        entry = {'name':self.name, 'score':self.score, 'dist':self.dist, 'level':self.lvl, 'date':datetime.now().strftime("%Y-%m-%d")}
        self.scores.append(entry)
        self.scores.sort(key=lambda x:x['score'], reverse=True)
        self.scores = self.scores[:10]
        self.save_scores()
    
    def reset(self):
        self.player = Player(self.settings['color'])
        self.score = 0
        self.dist = 0
        self.lvl = 1
        self.spd = 5
        self.enemies = []
        self.obs = []
        self.power = None
        self.active = None
        self.shield = False
        self.power_end = 0
        self.spawn_timer = 0
        self.enemy_timer = 0
        self.obs_timer = 0
    
    def cur_speed(self):
        s = self.spd + (self.lvl-1)*0.5
        m = {'easy':0.8, 'medium':1.0, 'hard':1.3}[self.settings['diff']]
        if self.active == 1: s *= 1.8
        return s * m
    
    def update(self):
        speed = self.cur_speed()
        now = pygame.time.get_ticks()
        
        for e in self.enemies[:]:
            if e.update(): self.enemies.remove(e); self.score += 10
        
        for o in self.obs[:]:
            if o.update(): self.obs.remove(o)
        
        if self.power:
            if self.power.update() or self.power.expired():
                self.power = None
        
        if self.active and now > self.power_end:
            if self.active == 2: self.shield = False
            self.active = None
        
        self.dist += 1
        self.score += 1
        
        nl = self.dist // 500 + 1
        if nl > self.lvl: self.lvl = nl
        
        self.enemy_timer += 1
        if self.enemy_timer > max(30, 60 - self.lvl*2):
            self.enemy_timer = 0
            lane = random.randint(0, LANES-1)
            self.enemies.append(Enemy(lane, speed))
        
        if self.lvl >= 2:
            self.obs_timer += 1
            if self.obs_timer > 100:
                self.obs_timer = 0
                self.obs.append(Obstacle(random.randint(0, LANES-1), speed*0.8))
        
        if not self.power and self.lvl >= 2:
            self.spawn_timer += 1
            if self.spawn_timer > 300:
                self.spawn_timer = 0
                self.power = Power(random.randint(0, LANES-1), speed*0.6)
        
        for e in self.enemies[:]:
            if self.player.rect.colliderect(e.rect):
                if self.shield:
                    self.enemies.remove(e)
                    self.shield = False
                    self.active = None
                else:
                    self.add_score()
                    self.state = 2
                    return
        
        for o in self.obs[:]:
            if self.player.rect.colliderect(o.rect):
                if o.type in ['pothole','barrier']:
                    self.add_score()
                    self.state = 2
                    return
                self.obs.remove(o)
        
        if self.power and self.player.rect.colliderect(self.power.rect):
            if self.power.type == 1:
                self.active = 1
                self.power_end = now + 4000
            elif self.power.type == 2:
                self.shield = True
                self.active = 2
                self.power_end = now + 8000
            else:
                if self.obs: self.obs.pop(0)
                self.score += 50
            self.power = None
            self.score += 20
    
    def draw(self):
        if self.state == 1:
            self.screen.fill(DARK)
            for i in range(1, LANES):
                pygame.draw.line(self.screen, WHITE, (i*LW,0), (i*LW,H), 3)
            for e in self.enemies: e.draw(self.screen)
            for o in self.obs: o.draw(self.screen)
            if self.power: self.power.draw(self.screen)
            self.player.draw(self.screen)
            
            self.screen.blit(self.font.render(f"Score:{self.score}",1,WHITE), (10,10))
            self.screen.blit(self.font.render(f"Dist:{self.dist}",1,WHITE), (10,40))
            self.screen.blit(self.font.render(f"Lvl:{self.lvl}",1,WHITE), (10,70))
            if self.active:
                n = {1:"NITRO",2:"SHIELD",3:"REPAIR"}[self.active]
                self.screen.blit(self.font.render(f"POWER:{n}",1,YELLOW), (W-150,10))
            if self.shield:
                self.screen.blit(self.font.render("SHIELD",1,CYAN), (W-150,40))
        
        elif self.state == 0:
            self.screen.fill(BLACK)
            t = self.big.render("RACER GAME",1,RED)
            self.screen.blit(t, t.get_rect(center=(W//2,80)))
            
            prompt = self.font.render("ENTER YOUR NAME:",1,WHITE)
            self.screen.blit(prompt, prompt.get_rect(center=(W//2,160)))
            
            rect = pygame.Rect(W//2-150, 190, 300, 40)
            pygame.draw.rect(self.screen, WHITE, rect, 2)
            
            name_text = self.font.render(self.name + ("|" if self.name_active else ""),1,WHITE)
            self.screen.blit(name_text, (rect.x+10, rect.y+8))
            
            inst = self.font.render("Press ENTER when done",1,GRAY)
            self.screen.blit(inst, inst.get_rect(center=(W//2,260)))
            
            if self.name:
                btns = [("PLAY",340), ("SCORES",400), ("SETTINGS",460), ("QUIT",520)]
                mx,my = pygame.mouse.get_pos()
                for txt,y in btns:
                    r = self.font.render(txt,1,WHITE).get_rect(center=(W//2,y))
                    col = YELLOW if r.collidepoint(mx,my) else WHITE
                    self.screen.blit(self.font.render(txt,1,col), r)
            else:
                hint = self.font.render("Type your name above",1,GRAY)
                self.screen.blit(hint, hint.get_rect(center=(W//2,340)))
        
        elif self.state == 2:
            o = pygame.Surface((W,H)); o.set_alpha(200); o.fill(BLACK)
            self.screen.blit(o,(0,0))
            t = self.big.render("GAME OVER",1,RED)
            self.screen.blit(t, t.get_rect(center=(W//2,100)))
            self.screen.blit(self.font.render(f"Score:{self.score}",1,WHITE), self.font.render(f"Score:{self.score}",1,WHITE).get_rect(center=(W//2,200)))
            self.screen.blit(self.font.render("PLAY AGAIN",1,YELLOW), self.font.render("PLAY AGAIN",1,YELLOW).get_rect(center=(W//2,320)))
            self.screen.blit(self.font.render("MAIN MENU",1,YELLOW), self.font.render("MAIN MENU",1,YELLOW).get_rect(center=(W//2,380)))
        
        elif self.state == 3:
            self.screen.fill(BLACK)
            t = self.big.render("TOP 10",1,YELLOW)
            self.screen.blit(t, t.get_rect(center=(W//2,50)))
            for i,s in enumerate(self.scores[:10],1):
                y = 120 + i*35
                self.screen.blit(self.font.render(str(i),1,WHITE), (50,y))
                self.screen.blit(self.font.render(s['name'][:12],1,WHITE), (120,y))
                self.screen.blit(self.font.render(str(s['score']),1,WHITE), (300,y))
                self.screen.blit(self.font.render(str(s['level']),1,WHITE), (450,y))
            b = self.font.render("BACK",1,YELLOW)
            self.back = b.get_rect(center=(W//2, H-50))
            self.screen.blit(b, self.back)
        
        elif self.state == 4:
            self.screen.fill(BLACK)
            t = self.big.render("SETTINGS",1,YELLOW)
            self.screen.blit(t, t.get_rect(center=(W//2,50)))
            snd = self.font.render(f"Sound: {'ON' if self.settings['sound'] else 'OFF'}",1,WHITE)
            self.screen.blit(snd, snd.get_rect(center=(W//2,150)))
            diff = self.font.render(f"Difficulty: {self.settings['diff'].upper()}",1,WHITE)
            self.screen.blit(diff, diff.get_rect(center=(W//2,200)))
            col = self.font.render("Car Color: Click",1,WHITE)
            self.screen.blit(col, col.get_rect(center=(W//2,250)))
            pygame.draw.rect(self.screen, self.settings['color'], (W//2-30,270,60,40))
            sv = self.font.render("SAVE",1,GREEN)
            self.screen.blit(sv, sv.get_rect(center=(W//2, H-80)))
            self.btns = {'snd':snd.get_rect(center=(W//2,150)), 'diff':diff.get_rect(center=(W//2,200)), 'col':col.get_rect(center=(W//2,250)), 'sv':sv.get_rect(center=(W//2, H-80))}
        
        pygame.display.flip()
    
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                elif event.type == pygame.KEYDOWN:
                    if self.state == 1:
                        if event.key == pygame.K_LEFT:
                            self.player.left()
                        elif event.key == pygame.K_RIGHT:
                            self.player.right()
                    
                    elif self.state == 0:
                        if event.key == pygame.K_RETURN and self.name:
                            pass  
                        elif event.key == pygame.K_BACKSPACE:
                            self.name = self.name[:-1]
                        else:
                            if event.key != pygame.K_RETURN and event.unicode:
                                self.name += event.unicode
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.state == 0 and self.name:
                        mx, my = event.pos
                        r1 = self.font.render("PLAY",1,WHITE).get_rect(center=(W//2,340))
                        r2 = self.font.render("SCORES",1,WHITE).get_rect(center=(W//2,400))
                        r3 = self.font.render("SETTINGS",1,WHITE).get_rect(center=(W//2,460))
                        r4 = self.font.render("QUIT",1,WHITE).get_rect(center=(W//2,520))
                        if r1.collidepoint(mx,my):
                            self.reset()
                            self.state = 1
                        elif r2.collidepoint(mx,my):
                            self.state = 3
                        elif r3.collidepoint(mx,my):
                            self.state = 4
                        elif r4.collidepoint(mx,my):
                            running = False
                    
                    elif self.state == 2:
                        mx,my = event.pos
                        r1 = self.font.render("PLAY AGAIN",1,YELLOW).get_rect(center=(W//2,320))
                        r2 = self.font.render("MAIN MENU",1,YELLOW).get_rect(center=(W//2,380))
                        if r1.collidepoint(mx,my):
                            self.reset()
                            self.state = 1
                        elif r2.collidepoint(mx,my):
                            self.state = 0
                    
                    elif self.state == 3 and hasattr(self,'back') and self.back.collidepoint(event.pos):
                        self.state = 0
                    
                    elif self.state == 4:
                        if hasattr(self,'btns'):
                            mx,my = event.pos
                            if self.btns['snd'].collidepoint(mx,my):
                                self.settings['sound'] = not self.settings['sound']
                            elif self.btns['diff'].collidepoint(mx,my):
                                d = ['easy','medium','hard']
                                self.settings['diff'] = d[(d.index(self.settings['diff'])+1)%3]
                            elif self.btns['col'].collidepoint(mx,my):
                                cols = [BLUE,RED,GREEN,YELLOW,ORANGE]
                                self.settings['color'] = cols[(cols.index(self.settings['color'])+1)%len(cols)]
                            elif self.btns['sv'].collidepoint(mx,my):
                                self.save_settings()
                                self.state = 0
            
            if self.state == 1:
                self.update()
            
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()

if __name__ == "__main__":
    Game().run()