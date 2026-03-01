import os
import pygame
import yaml


WIDTH, HEIGHT = 1920, 1080

DIALOGUE_FRAME_SIZE = (1200, 300)
DIALOGUE_BOTTOM_PADDING = 10
DIALOGUE_FRAME_INNER_MARGIN_X = 40
DIALOGUE_NAME_OFFSET_Y = 20
DIALOGUE_TEXT_OFFSET_Y = 80

NAV_BUTTON_SIZE = (80, 80)
NAV_BUTTON_GAP = 20

SETTINGS_BUTTON_POS = (20, 20)
SETTINGS_BUTTON_SIZE = (100, 100)

FADE_IN_DURATION_MS = 450


def find_assets_dir():
    base = os.path.dirname(os.path.abspath(__file__))
    candidate = os.path.join(base, "menu_assets")
    if os.path.isdir(candidate):
        return candidate
    return base


def find_files(asset_dir, exts):
    exts = tuple(exts)
    return [f for f in os.listdir(asset_dir) if f.lower().endswith(exts)]


class Button:
    def __init__(self, text, rect, font, image=None, callback=None):
        self.text = text
        self.rect = pygame.Rect(rect)
        self.font = font
        self.image = image
        self.callback = callback
        self.hover = False

    def draw(self, surf):
        if self.image:
            iw, ih = self.image.get_size()
            # scale preserving aspect ratio to fit inside button rect
            scale = min(self.rect.w / iw, self.rect.h / ih)
            hover_scale = 1.10 if self.hover else 1.0
            new_w = max(1, int(iw * scale * hover_scale))
            new_h = max(1, int(ih * scale * hover_scale))
            img = pygame.transform.smoothscale(self.image, (new_w, new_h))
            px = self.rect.x + (self.rect.w - new_w) // 2
            py = self.rect.y + (self.rect.h - new_h) // 2

            if self.hover:
                glow_pad = 22
                glow_w = max(1, self.rect.w - glow_pad * 2)
                glow_h = max(1, self.rect.h - glow_pad * 2)

                glow_x = self.rect.centerx - glow_w // 2
                glow_y = self.rect.centery - glow_h // 2

                surf_w, surf_h = surf.get_size()
                max_half_w = min(self.rect.centerx, surf_w - self.rect.centerx)
                max_half_h = min(self.rect.centery, surf_h - self.rect.centery)

                glow_w = min(glow_w, max(1, max_half_w * 2))
                glow_h = min(glow_h, max(1, max_half_h * 2))

                glow_x = self.rect.centerx - glow_w // 2
                glow_y = self.rect.centery - glow_h // 2

                glow = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
                pygame.draw.rect(glow, (220, 20, 20, 50), glow.get_rect(), border_radius=14)
                pygame.draw.rect(glow, (220, 20, 20, 160), glow.get_rect(), 6, border_radius=14)
                surf.blit(glow, (glow_x, glow_y))
                
            surf.blit(img, (px, py))
            return
        else:
            color = (180, 20, 20) if not self.hover else (220, 40, 40)
            pygame.draw.rect(surf, color, self.rect, border_radius=6)
            pygame.draw.rect(surf, (30, 10, 10), self.rect, 4, border_radius=6)

        # draw text centered
        txt = self.font.render(self.text, True, (255, 255, 255))
        tx = txt.get_rect(center=self.rect.center)
        surf.blit(txt, tx)

    def handle_event(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.rect.collidepoint(ev.pos):
                if self.callback:
                    self.callback()


def load_assets(asset_dir):
    imgs = find_files(asset_dir, ('.png', '.jpg', '.jpeg'))
    fonts = find_files(asset_dir, ('.ttf', '.otf'))

    # map known asset names to files present in the folder
    name_map = {n.lower(): os.path.join(asset_dir, n) for n in imgs}

    bg_path = None
    play_btn = None
    title_btn = None
    exit_btn = None

    # common filenames used in your assets
    if 'menu_bg.png' in name_map:
        bg_path = name_map['menu_bg.png']
    else:
        # fallback to any image
        bg_path = os.path.join(asset_dir, imgs[0]) if imgs else None

    if 'playbutton.png' in name_map:
        play_btn = name_map['playbutton.png']
    if 'titlebutton.png' in name_map:
        title_btn = name_map['titlebutton.png']
    if 'exitbutton.png' in name_map:
        exit_btn = name_map['exitbutton.png']

    font_path = os.path.join(asset_dir, fonts[0]) if fonts else None
    return bg_path, play_btn, title_btn, exit_btn, font_path


class Game:
    """Handles the visual novel gameplay and dialogue display"""
    
    def __init__(self, screen, clock, font_names, font_dialogues, base_dir):
        self.screen = screen
        self.clock = clock
        self.font_names = font_names
        self.font_dialogues = font_dialogues
        self.base_dir = base_dir
        self.scenes = []
        self.current_scene_idx = 0
        self.current_dialogue_idx = 0
        self.background = None
        self.character_image = None
        self.dialogue_frame = None
        self.back_button = None
        self.forward_button = None
        self.back_button_rect = None
        self.forward_button_rect = None
        self.hexagon_icon = None
        self.hexagon_icon_rect = None
        self.settings_open = False
        self._fade_in_start_ms = None
        self._fade_overlay = pygame.Surface((WIDTH, HEIGHT))
        self._fade_overlay.fill((0, 0, 0))
        self.is_running = True
        
        # Load dialogue frame and buttons from hud_assets
        self.load_dialogue_frame()
        self.load_navigation_buttons()
        self.load_hexagon_icon()
        
        # Load dialogues from YAML
        self.load_dialogues()
        
        # Load initial scene
        if self.scenes:
            self.load_scene(0)

        self._start_fade_in()

    def _start_fade_in(self):
        self._fade_in_start_ms = pygame.time.get_ticks()
    
    def load_dialogue_frame(self):
        """Load dialogue frame image from hud_assets"""
        frame_path = os.path.join(self.base_dir, 'hud_assets', 'dialogueframe.png')
        if os.path.isfile(frame_path):
            try:
                self.dialogue_frame = pygame.image.load(frame_path)
                self.dialogue_frame = pygame.transform.smoothscale(self.dialogue_frame, DIALOGUE_FRAME_SIZE)
                self.dialogue_frame = self.dialogue_frame.convert_alpha()
                print(f"Loaded dialogue frame from {frame_path}")
            except Exception as e:
                print(f"Error loading dialogue frame: {e}")
        else:
            print(f"Dialogue frame not found at {frame_path}")
    
    def load_navigation_buttons(self):
        """Load navigation button images from hud_assets"""
        hud_dir = os.path.join(self.base_dir, 'hud_assets')
        
        # Load back button
        back_path = os.path.join(hud_dir, 'backbutton.png')
        if os.path.isfile(back_path):
            try:
                self.back_button = pygame.image.load(back_path)
                self.back_button = pygame.transform.smoothscale(self.back_button, NAV_BUTTON_SIZE)
                self.back_button = self.back_button.convert_alpha()
                print(f"Loaded back button from {back_path}")
            except Exception as e:
                print(f"Error loading back button: {e}")
        
        # Load forward button
        forward_path = os.path.join(hud_dir, 'forwardbutton.png')
        if os.path.isfile(forward_path):
            try:
                self.forward_button = pygame.image.load(forward_path)
                self.forward_button = pygame.transform.smoothscale(self.forward_button, NAV_BUTTON_SIZE)
                self.forward_button = self.forward_button.convert_alpha()
                print(f"Loaded forward button from {forward_path}")
            except Exception as e:
                print(f"Error loading forward button: {e}")

    def load_hexagon_icon(self):
        hud_dir = os.path.join(self.base_dir, 'hud_assets')
        hexagon_path = os.path.join(hud_dir, 'hexagon_icon.png')
        if os.path.isfile(hexagon_path):
            try:
                self.hexagon_icon = pygame.image.load(hexagon_path)
                self.hexagon_icon = pygame.transform.smoothscale(self.hexagon_icon, SETTINGS_BUTTON_SIZE)
                self.hexagon_icon = self.hexagon_icon.convert_alpha()
                print(f"Loaded hexagon icon from {hexagon_path}")
            except Exception as e:
                print(f"Error loading hexagon icon: {e}")
    
    def load_dialogues(self):
        """Load narrative from dialogues.yml"""
        yaml_path = os.path.join(self.base_dir, 'dialogues.yml')
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and 'scenes' in data:
                    self.scenes = data['scenes']
                    print(f"Loaded {len(self.scenes)} scenes from dialogues.yml")
        except FileNotFoundError:
            print(f"dialogues.yml not found at {yaml_path}")
        except yaml.YAMLError as e:
            print(f"Error parsing dialogues.yml: {e}")

    def _get_scene_background_path(self, scene):
        return scene.get('background')

    def _get_scene_title(self, scene):
        return scene.get('name') or scene.get('scene') or scene.get('id') or 'Unknown'

    def _get_scene_id(self, scene):
        return scene.get('id') or scene.get('scene') or 'Unknown'

    def _get_dialogue_speaker(self, dialogue):
        return dialogue.get('speaker') or dialogue.get('character') or 'Unknown'

    def _get_dialogue_text(self, dialogue):
        return dialogue.get('text', '')

    def _get_dialogue_sprite_path(self, dialogue):
        return dialogue.get('sprite') or dialogue.get('character_image')
    
    def load_scene(self, scene_idx):
        """Load a scene by index"""
        if scene_idx >= len(self.scenes):
            self.is_running = False
            return
        
        self.current_scene_idx = scene_idx
        self.current_dialogue_idx = 0
        scene = self.scenes[scene_idx]
        
        # Load background if specified
        bg_rel_path = self._get_scene_background_path(scene)
        if bg_rel_path:
            bg_path = os.path.join(self.base_dir, bg_rel_path)
            self.background = self.load_image(bg_path)
        else:
            self.background = None
        
        print(f"Loaded scene: {self._get_scene_id(scene)}")
        self._start_fade_in()
    
    def load_image(self, path):
        """Safely load an image file"""
        if path and os.path.isfile(path):
            try:
                img = pygame.image.load(path)
                img = pygame.transform.smoothscale(img, (WIDTH, HEIGHT))
                return img.convert()
            except Exception as e:
                print(f"Error loading image {path}: {e}")
        return None
    
    def get_current_dialogue(self):
        """Get the current dialogue line"""
        if self.current_scene_idx < len(self.scenes):
            scene = self.scenes[self.current_scene_idx]
            if 'dialogues' in scene and self.current_dialogue_idx < len(scene['dialogues']):
                return scene['dialogues'][self.current_dialogue_idx]
        return None
    
    def previous_dialogue(self):
        """Move to previous dialogue"""
        if self.current_dialogue_idx > 0:
            self.current_dialogue_idx -= 1
        elif self.current_scene_idx > 0:
            # Go to previous scene
            prev_scene_idx = self.current_scene_idx - 1
            self.load_scene(prev_scene_idx)
            scene = self.scenes[self.current_scene_idx]
            dialogues = scene.get('dialogues') or []
            self.current_dialogue_idx = max(0, len(dialogues) - 1)
    
    def next_dialogue(self):
        """Move to next dialogue or next scene"""
        if self.current_scene_idx >= len(self.scenes):
            return
        
        scene = self.scenes[self.current_scene_idx]
        if self.current_dialogue_idx < len(scene['dialogues']) - 1:
            self.current_dialogue_idx += 1
        else:
            # Move to next scene
            if self.current_scene_idx < len(self.scenes) - 1:
                self.load_scene(self.current_scene_idx + 1)
            else:
                # End of story
                self.is_running = False
    
    def handle_events(self):
        """Handle input events"""
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.is_running = False
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if self.hexagon_icon_rect and self.hexagon_icon_rect.collidepoint(ev.pos):
                    self.settings_open = not self.settings_open
                    continue
                # forwardbutton scrolls dialogue BACK, backbutton scrolls dialogue FORWARD
                if self.forward_button_rect and self.forward_button_rect.collidepoint(ev.pos):
                    self.previous_dialogue()
                elif self.back_button_rect and self.back_button_rect.collidepoint(ev.pos):
                    self.next_dialogue()
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_LEFT:
                    self.previous_dialogue()
                elif ev.key == pygame.K_RIGHT:
                    self.next_dialogue()
                elif ev.key == pygame.K_ESCAPE:
                    self.is_running = False
    
    def draw(self):
        """Draw the current dialogue frame"""
        # Draw background
        if self.background:
            self.screen.blit(self.background, (0, 0))
        else:
            self.screen.fill((20, 20, 20))

        mouse_pos = pygame.mouse.get_pos()

        if self.hexagon_icon:
            self.hexagon_icon_rect = pygame.Rect(SETTINGS_BUTTON_POS, SETTINGS_BUTTON_SIZE)
            self.screen.blit(self.hexagon_icon, self.hexagon_icon_rect)
        
        dialogue = self.get_current_dialogue()
        if dialogue:
            character_name = self._get_dialogue_speaker(dialogue)
            dialogue_text = self._get_dialogue_text(dialogue)
            
            # Draw dialogue frame from hud_assets
            box_height = DIALOGUE_FRAME_SIZE[1]
            bottom_padding = DIALOGUE_BOTTOM_PADDING
            box_y = HEIGHT - box_height - bottom_padding

            button_size = NAV_BUTTON_SIZE[0]
            gap = NAV_BUTTON_GAP
            frame_w = self.dialogue_frame.get_width() if self.dialogue_frame else DIALOGUE_FRAME_SIZE[0]
            total_w = button_size + gap + frame_w + gap + button_size
            start_x = (WIDTH - total_w) // 2
            forward_x = start_x
            frame_x = forward_x + button_size + gap
            back_x = frame_x + frame_w + gap

            if self.dialogue_frame:
                self.screen.blit(self.dialogue_frame, (frame_x, box_y))
            else:
                # Fallback: draw semi-transparent dark rectangle sized like the frame (not full width)
                box_rect = pygame.Rect(frame_x, box_y, frame_w, box_height)
                s = pygame.Surface((frame_w, box_height), pygame.SRCALPHA)
                pygame.draw.rect(s, (0, 0, 0, 200), (0, 0, frame_w, box_height))
                self.screen.blit(s, (frame_x, box_y))
                pygame.draw.rect(self.screen, (220, 20, 20), box_rect, 3)
            
            # Draw character name with YDKJ_The_Ride font
            name_surf = self.font_names.render(character_name.upper(), True, (220, 20, 20))
            self.screen.blit(name_surf, (frame_x + DIALOGUE_FRAME_INNER_MARGIN_X, box_y + DIALOGUE_NAME_OFFSET_Y))
            
            # Draw dialogue text with word wrapping using Caslon Antique font
            margin_x = DIALOGUE_FRAME_INNER_MARGIN_X
            margin_y = box_y + DIALOGUE_TEXT_OFFSET_Y
            max_width = frame_w - 2 * margin_x
            
            # Simple word wrapping
            words = dialogue_text.split()
            lines = []
            current_line = ""
            
            for word in words:
                test_line = current_line + " " + word if current_line else word
                text_width = self.font_dialogues.size(test_line)[0]
                if text_width > max_width:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
                else:
                    current_line = test_line
            
            if current_line:
                lines.append(current_line)
            
            # Draw lines
            for i, line in enumerate(lines):
                if i < 3:  # Limit to 3 lines
                    line_surf = self.font_dialogues.render(line, True, (255, 255, 255))
                    self.screen.blit(line_surf, (frame_x + margin_x, margin_y + i * 50))
            
            # Draw navigation buttons
            button_y = box_y + (box_height - NAV_BUTTON_SIZE[1]) // 2

            def blit_hover_scaled(img, rect, scale_down=0.92):
                if rect.collidepoint(mouse_pos):
                    w = max(1, int(rect.w * scale_down))
                    h = max(1, int(rect.h * scale_down))
                    scaled = pygame.transform.smoothscale(img, (w, h))
                    x = rect.x + (rect.w - w) // 2
                    y = rect.y + (rect.h - h) // 2
                    self.screen.blit(scaled, (x, y))
                else:
                    self.screen.blit(img, rect)
            
            # forwardbutton is LEFT
            if self.forward_button:
                self.forward_button_rect = pygame.Rect(forward_x, button_y, NAV_BUTTON_SIZE[0], NAV_BUTTON_SIZE[1])
                blit_hover_scaled(self.forward_button, self.forward_button_rect)
            
            # backbutton is RIGHT
            if self.back_button:
                self.back_button_rect = pygame.Rect(back_x, button_y, NAV_BUTTON_SIZE[0], NAV_BUTTON_SIZE[1])
                blit_hover_scaled(self.back_button, self.back_button_rect)
        
        if self._fade_in_start_ms is not None:
            elapsed = pygame.time.get_ticks() - self._fade_in_start_ms
            if elapsed >= FADE_IN_DURATION_MS:
                self._fade_in_start_ms = None
            else:
                alpha = int(255 * (1.0 - (elapsed / FADE_IN_DURATION_MS)))
                if alpha > 0:
                    self._fade_overlay.set_alpha(alpha)
                    self.screen.blit(self._fade_overlay, (0, 0))

        pygame.display.flip()
    
    def run(self):
        """Main game loop"""
        while self.is_running:
            self.handle_events()
            self.draw()
            self.clock.tick(60)





def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption('Dexter - The Game (Menu)')
    clock = pygame.time.Clock()

    asset_dir = find_assets_dir()
    bg_path, play_btn_path, title_btn_path, exit_btn_path, font_path = load_assets(asset_dir)

    # load background
    background = None
    if bg_path and os.path.isfile(bg_path):
        try:
            background = pygame.image.load(bg_path).convert()
            background = pygame.transform.smoothscale(background, (WIDTH, HEIGHT))
        except Exception:
            background = None

    # load button images
    def load_img(path, convert_alpha=True):
        if path and os.path.isfile(path):
            try:
                img = pygame.image.load(path)
                print(f'Loaded image: {os.path.basename(path)} size={img.get_size()}')
                return img.convert_alpha() if convert_alpha else img.convert()
            except Exception:
                return None
        return None

    play_img = load_img(play_btn_path)
    title_img = load_img(title_btn_path)
    exit_img = load_img(exit_btn_path)

    # load font
    if font_path and os.path.isfile(font_path):
        try:
            base_font = pygame.font.Font(font_path, 56)
            small_font = pygame.font.Font(font_path, 36)
        except Exception:
            base_font = pygame.font.SysFont(None, 56)
            small_font = pygame.font.SysFont(None, 36)
    else:
        base_font = pygame.font.SysFont(None, 56)
        small_font = pygame.font.SysFont(None, 36)
    
    # Load game fonts
    game_fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'game_fonts')
    font_names = None
    font_dialogues = None
    
    # Load YDKJ_The_Ride font for character names
    ydkj_path = os.path.join(game_fonts_dir, 'YDKJ_The_Ride2_0.ttf')
    if os.path.isfile(ydkj_path):
        try:
            font_names = pygame.font.Font(ydkj_path, 48)
            print(f"Loaded YDKJ_The_Ride font from {ydkj_path}")
        except Exception as e:
            print(f"Error loading YDKJ_The_Ride font: {e}")
            font_names = pygame.font.SysFont(None, 48)
    else:
        font_names = pygame.font.SysFont(None, 48)
    
    # Load Caslon Antique font for dialogue text
    caslon_path = os.path.join(game_fonts_dir, 'Caslon Antique.ttf')
    if os.path.isfile(caslon_path):
        try:
            font_dialogues = pygame.font.Font(caslon_path, 36)
            print(f"Loaded Caslon Antique font from {caslon_path}")
        except Exception as e:
            print(f"Error loading Caslon Antique font: {e}")
            font_dialogues = pygame.font.SysFont(None, 36)
    else:
        font_dialogues = pygame.font.SysFont(None, 36)

    
    btn_w, btn_h = 900, 220
    left_x = -90
    start_y = 360
    gap = 5

    # Game state management
    state = {'current': 'menu', 'game': None}

    def on_play():
        """Start the game"""
        state['game'] = Game(screen, clock, font_names, font_dialogues, os.path.dirname(os.path.abspath(__file__)))
        state['current'] = 'game'

    def on_quit():
        state['current'] = 'quit'

    # Play button now starts the game
    btn_play = Button('ИГРАТЬ', (left_x, start_y, btn_w, btn_h), base_font, image=play_img, callback=on_play)
    btn_credits = Button('ТИТРЫ', (left_x, start_y + (btn_h + gap), btn_w, btn_h), base_font, image=title_img, callback=None)
    btn_quit = Button('ВЫХОД', (left_x, start_y + 2 * (btn_h + gap), btn_w, btn_h), base_font, image=exit_img, callback=on_quit)

    buttons = [btn_play, btn_credits, btn_quit]

    # Main loop
    running = True
    while running:
        if state['current'] == 'menu':
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                for b in buttons:
                    b.handle_event(ev)

            # draw menu
            if background:
                screen.blit(background, (0, 0))
            else:
                screen.fill((10, 10, 10))
            for b in buttons:
                b.draw(screen)

            pygame.display.flip()
            clock.tick(60)

        elif state['current'] == 'game':
            # Game state
            if state['game']:
                state['game'].run()
            # После завершения игры возвращаемся в меню
            state['current'] = 'menu'

        elif state['current'] == 'quit':
            running = False

    pygame.quit()


if __name__ == '__main__':
    main()
