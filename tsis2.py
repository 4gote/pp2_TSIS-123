import pygame
import sys
import math
from datetime import datetime

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
TOOLBAR_HEIGHT = 80
CANVAS_WIDTH = SCREEN_WIDTH
CANVAS_HEIGHT = SCREEN_HEIGHT - TOOLBAR_HEIGHT

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (64, 64, 64)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)

COLORS = [BLACK, RED, GREEN, BLUE, YELLOW, CYAN, MAGENTA, ORANGE, PURPLE]
COLOR_NAMES = ["BLK", "RED", "GRN", "BLU", "YEL", "CYN", "MAG", "ORN", "PRP"]

class PaintApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Paint App")
        
        self.canvas = pygame.Surface((CANVAS_WIDTH, CANVAS_HEIGHT))
        self.canvas.fill(WHITE)
        
        self.tool = 0
        self.color = BLACK
        self.brush_size = 5
        self.drawing = False
        self.start = None
        self.last = None
        
        self.text_mode = False
        self.text_pos = None
        self.text_content = ""
        self.font = pygame.font.SysFont('Arial', 24)
        
        self.setup_buttons()
        self.clock = pygame.time.Clock()
    
    def setup_buttons(self):
        bw, bh = 50, 40
        spacing = 5
        y = TOOLBAR_HEIGHT // 2 - bh // 2
        
        tools = ["PEN", "LINE", "RECT", "CIRC", "SQR", "TRI", "RHO", "ERA", "FILL", "TXT"]
        self.tool_buttons = []
        for i, label in enumerate(tools):
            x = 10 + i * (bw + spacing)
            self.tool_buttons.append((pygame.Rect(x, y, bw, bh), label, i))
        
        self.color_buttons = []
        color_x = 10 + len(tools) * (bw + spacing) + 20
        for i, color in enumerate(COLORS):
            x = color_x + i * (bw + spacing)
            self.color_buttons.append((pygame.Rect(x, y, bw, bh), color, COLOR_NAMES[i]))
        
        self.size_buttons = []
        size_x = color_x + len(COLORS) * (bw + spacing) + 20
        sizes = [(2, "S"), (5, "M"), (10, "L")]
        for i, (size, label) in enumerate(sizes):
            x = size_x + i * (bw + spacing)
            self.size_buttons.append((pygame.Rect(x, y, bw, bh), size, label))
        
        self.save_btn = pygame.Rect(size_x + len(sizes) * (bw + spacing) + 20, y, bw, bh)
    
    def draw_ui(self):
        pygame.draw.rect(self.screen, GRAY, (0, 0, SCREEN_WIDTH, TOOLBAR_HEIGHT))
        pygame.draw.line(self.screen, DARK_GRAY, (0, TOOLBAR_HEIGHT), (SCREEN_WIDTH, TOOLBAR_HEIGHT), 3)
        
        for rect, label, idx in self.tool_buttons:
            color = CYAN if idx == self.tool else DARK_GRAY
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, BLACK, rect, 2)
            text = pygame.font.SysFont('Arial', 12).render(label, True, WHITE)
            self.screen.blit(text, text.get_rect(center=rect.center))
        
        for rect, color, label in self.color_buttons:
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, BLACK, rect, 2)
            if color == self.color:
                pygame.draw.rect(self.screen, YELLOW, rect, 3)
        
        for rect, size, label in self.size_buttons:
            color = CYAN if size == self.brush_size else DARK_GRAY
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, BLACK, rect, 2)
            text = pygame.font.SysFont('Arial', 14).render(label, True, WHITE)
            self.screen.blit(text, text.get_rect(center=rect.center))
        
        pygame.draw.rect(self.screen, GREEN, self.save_btn)
        pygame.draw.rect(self.screen, BLACK, self.save_btn, 2)
        text = pygame.font.SysFont('Arial', 12).render("SAVE", True, WHITE)
        self.screen.blit(text, text.get_rect(center=self.save_btn.center))
        
        mx, my = pygame.mouse.get_pos()
        if my > TOOLBAR_HEIGHT and self.tool in [0, 7]:
            pygame.draw.circle(self.screen, RED, (mx, my), self.brush_size, 1)
    
    def draw_shape(self, start, end):
        x1, y1 = start
        x2, y2 = end
        w, h = abs(x2 - x1), abs(y2 - y1)
        left, top = min(x1, x2), min(y1, y2)
        
        if self.tool == 2:
            pygame.draw.rect(self.canvas, self.color, (left, top, w, h), self.brush_size)
        elif self.tool == 3:
            r = int(math.sqrt(w**2 + h**2) / 2)
            center = ((x1 + x2) // 2, (y1 + y2) // 2)
            pygame.draw.circle(self.canvas, self.color, center, r, self.brush_size)
        elif self.tool == 4:
            s = max(w, h)
            pygame.draw.rect(self.canvas, self.color, (left, top, s, s), self.brush_size)
        elif self.tool == 5:
            points = [(x1, y1), (x2, y1), (x1, y2)]
            pygame.draw.polygon(self.canvas, self.color, points, self.brush_size)
        elif self.tool == 6:
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            points = [(cx, cy - h//2), (cx + w//2, cy), (cx, cy + h//2), (cx - w//2, cy)]
            pygame.draw.polygon(self.canvas, self.color, points, self.brush_size)
    
    def flood_fill(self, pos, target):
        stack = [pos]
        visited = set()
        pixels = pygame.PixelArray(self.canvas)
        
        while stack:
            x, y = stack.pop()
            if x < 0 or x >= CANVAS_WIDTH or y < 0 or y >= CANVAS_HEIGHT:
                continue
            if (x, y) in visited:
                continue
            if pixels[x, y][:3] != target:
                continue
            pixels[x, y] = self.color
            visited.add((x, y))
            stack.extend([(x+1, y), (x-1, y), (x, y+1), (x, y-1)])
        
        pixels.close()
    
    def run(self):
        running = True
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                if self.text_mode:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_RETURN and self.text_content:
                            text_surf = self.font.render(self.text_content, True, self.color)
                            self.canvas.blit(text_surf, self.text_pos)
                            self.text_mode = False
                        elif event.key == pygame.K_ESCAPE:
                            self.text_mode = False
                        elif event.key == pygame.K_BACKSPACE:
                            self.text_content = self.text_content[:-1]
                        else:
                            self.text_content += event.unicode
                    continue
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        pygame.image.save(self.canvas, f"canvas_{timestamp}.png")
                        print(f"Saved: canvas_{timestamp}.png")
                    elif event.key == pygame.K_1:
                        self.brush_size = 2
                    elif event.key == pygame.K_2:
                        self.brush_size = 5
                    elif event.key == pygame.K_3:
                        self.brush_size = 10
                
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    
                    if my < TOOLBAR_HEIGHT:
                        for rect, label, idx in self.tool_buttons:
                            if rect.collidepoint(mx, my):
                                self.tool = idx
                        for rect, color, _ in self.color_buttons:
                            if rect.collidepoint(mx, my):
                                self.color = color
                        for rect, size, _ in self.size_buttons:
                            if rect.collidepoint(mx, my):
                                self.brush_size = size
                        if self.save_btn.collidepoint(mx, my):
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            pygame.image.save(self.canvas, f"canvas_{timestamp}.png")
                            print(f"Saved: canvas_{timestamp}.png")
                    else:
                        canvas_pos = (mx, my - TOOLBAR_HEIGHT)
                        
                        if self.tool == 0 or self.tool == 7:
                            self.drawing = True
                            self.last = canvas_pos
                            color = WHITE if self.tool == 7 else self.color
                            pygame.draw.circle(self.canvas, color, canvas_pos, self.brush_size)
                        
                        elif self.tool == 8:
                            target = self.canvas.get_at(canvas_pos)[:3]
                            if target != self.color:
                                self.flood_fill(canvas_pos, target)
                        
                        elif self.tool == 9:
                            self.text_mode = True
                            self.text_pos = canvas_pos
                            self.text_content = ""
                        
                        else:
                            self.drawing = True
                            self.start = canvas_pos
                
                if event.type == pygame.MOUSEMOTION and self.drawing:
                    mx, my = event.pos
                    if my > TOOLBAR_HEIGHT:
                        canvas_pos = (mx, my - TOOLBAR_HEIGHT)
                        
                        if self.tool == 0 or self.tool == 7:
                            color = WHITE if self.tool == 7 else self.color
                            pygame.draw.line(self.canvas, color, self.last, canvas_pos, self.brush_size * 2)
                            self.last = canvas_pos
                        elif self.tool == 1 and self.start:
                            self.screen.blit(self.canvas, (0, TOOLBAR_HEIGHT))
                            pygame.draw.line(self.screen, self.color, 
                                           (self.start[0], self.start[1] + TOOLBAR_HEIGHT),
                                           (mx, my), self.brush_size)
                
                if event.type == pygame.MOUSEBUTTONUP and self.drawing and self.start:
                    mx, my = event.pos
                    if my > TOOLBAR_HEIGHT:
                        end = (mx, my - TOOLBAR_HEIGHT)
                        
                        if self.tool == 1:
                            pygame.draw.line(self.canvas, self.color, self.start, end, self.brush_size)
                        elif self.tool >= 2 and self.tool <= 6:
                            self.draw_shape(self.start, end)
                    
                    self.drawing = False
                    self.start = None
            
            self.screen.blit(self.canvas, (0, TOOLBAR_HEIGHT))
            self.draw_ui()
            
            if self.text_mode and self.text_pos:
                preview = self.font.render(self.text_content + "|", True, self.color)
                self.screen.blit(preview, (self.text_pos[0], self.text_pos[1] + TOOLBAR_HEIGHT))
            
            pygame.display.flip()
            self.clock.tick(60)
        
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    app = PaintApp()
    app.run()