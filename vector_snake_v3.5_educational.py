"""
Vector Snake - Version 3.5 (Educational Edition)
================================================

A polished Snake game demonstrating intermediate-to-advanced game development
patterns in Python with Pygame. Suitable for teaching:

- Game loop architecture (fixed timestep with interpolation)
- State machine patterns for game flow
- Particle systems and visual effects
- Input buffering for responsive controls
- Performance optimization techniques
- Clean separation of concerns

CONTROLS:
    WASD / Arrow Keys  - Move snake
    Shift (hold)       - Boost speed (2x points, higher risk)
    P / ESC            - Pause
    F1                 - Toggle scanline effect
    Space / Enter      - Start / Restart

ARCHITECTURE OVERVIEW:
    
    ┌─────────────────────────────────────────────────────────────┐
    │                        main()                                │
    │  Game loop: events → update(dt) → draw() → flip             │
    └─────────────────────────────────────────────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                         Game                                 │
    │  - Owns all game objects (Snake, Fruit, effects)            │
    │  - Manages GameState transitions                            │
    │  - Coordinates update/draw across subsystems                │
    └─────────────────────────────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │    Snake     │   │    Fruit     │   │   Effects    │
    │  - Movement  │   │  - Animation │   │  - Particles │
    │  - Collision │   │  - Drawing   │   │  - Shake     │
    │  - Drawing   │   │              │   │  - Vignette  │
    └──────────────┘   └──────────────┘   └──────────────┘

BUG FIXES IN THIS VERSION:
    - Fixed: Pause overlay was created every frame (now checks state properly)
    - Fixed: grid_active_surf alpha modification affects cached surface permanently
            (should use per-blit alpha or copy)

Author: Educational refactor
Version: 3.5
"""

import sys
import random
import math
import json
import itertools
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Deque, Optional
from enum import Enum, auto
from collections import deque

import pygame
from pygame.math import Vector2


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def lerp_color(
    c1: Tuple[int, int, int], 
    c2: Tuple[int, int, int], 
    t: float
) -> Tuple[int, int, int]:
    """
    Linear interpolation between two RGB colors.
    
    This is fundamental to smooth color transitions in games. Instead of
    jumping from color A to color B, we can smoothly blend between them.
    
    Args:
        c1: Starting color as (R, G, B) tuple, values 0-255
        c2: Ending color as (R, G, B) tuple, values 0-255
        t: Interpolation factor, 0.0 = c1, 1.0 = c2, 0.5 = halfway
    
    Returns:
        Interpolated color as (R, G, B) tuple
    
    Example:
        >>> lerp_color((255, 0, 0), (0, 0, 255), 0.5)
        (127, 0, 127)  # Purple - halfway between red and blue
    
    The formula for each channel is: result = start + (end - start) * t
    This is equivalent to: result = start * (1 - t) + end * t
    """
    # Clamp t to valid range to prevent color overflow
    t = max(0.0, min(1.0, t))
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class Config:
    """
    Centralized game configuration using Python's dataclass decorator.
    
    WHY USE A CONFIG CLASS?
    -----------------------
    1. Single source of truth: All magic numbers in one place
    2. Easy tweaking: Adjust game feel without hunting through code
    3. Serialization ready: Could easily save/load from JSON
    4. Type hints: IDE can autocomplete and catch errors
    
    DESIGN PRINCIPLE: "No magic numbers in game logic"
    Instead of writing `if score > 100:`, write `if score > cfg.win_score:`
    This makes the code self-documenting and easily adjustable.
    """
    
    # === GRID SETTINGS ===
    # The game world is a grid of cells. Each cell can hold one snake segment or fruit.
    cell_size: int = 20      # Pixels per grid cell (affects visual density)
    grid_size: int = 30      # Grid is 30x30 cells = 900 possible positions
    fps: int = 60            # Target frame rate (display refresh rate)

    # === MOVEMENT TIMING ===
    # Snake moves in discrete steps, not continuously. These control step frequency.
    # Lower ms = faster movement. This creates the classic "snake" feel.
    base_move_ms: int = 120   # Milliseconds between moves (normal speed)
    boost_move_ms: int = 50   # Milliseconds between moves (boosting)
    
    # === DEATH EFFECT ===
    death_slowdown_duration: float = 1.5  # Seconds of slow-motion on death

    # === SCORING ===
    base_score: int = 1           # Points per fruit (normal)
    boost_multiplier: float = 2.0  # Score multiplier when boosting (risk/reward)

    # === VISUAL EFFECTS ===
    trail_length: int = 5              # How many previous positions to show as ghosts
    trail_alpha_decay: float = 0.6     # How quickly trail fades (0-1, lower = faster fade)
    scanlines_enabled: bool = True     # CRT scanline effect toggle
    scanline_alpha: int = 20           # Scanline darkness (0-255)
    vignette_base_alpha: int = 40      # Edge darkening intensity
    vignette_boost_pulse_amount: int = 30  # Extra vignette when boosting

    # === COLOR PALETTE ===
    # Neon/vector aesthetic with dark background and bright elements
    # Colors are RGB tuples: (Red, Green, Blue), each 0-255
    
    # Background and grid
    bg: Tuple[int, int, int] = (10, 10, 16)           # Near-black with slight blue
    grid_base: Tuple[int, int, int] = (20, 20, 30)    # Subtle grid lines
    grid_active: Tuple[int, int, int] = (40, 40, 60)  # Grid flash on fruit eat

    # Snake colors (gradient from head to tail)
    snake_head: Tuple[int, int, int] = (100, 255, 150)      # Bright green
    snake_body: Tuple[int, int, int] = (50, 200, 100)       # Medium green
    snake_tail: Tuple[int, int, int] = (30, 150, 80)        # Darker green
    snake_connector: Tuple[int, int, int] = (80, 255, 130)  # Lines between segments

    # Fruit colors
    fruit_core: Tuple[int, int, int] = (255, 60, 100)    # Hot pink center
    fruit_outer: Tuple[int, int, int] = (255, 100, 150)  # Lighter pink outer
    fruit_glow: Tuple[int, int, int] = (255, 80, 120)    # Glow effect

    # UI text colors
    text_main: Tuple[int, int, int] = (240, 240, 250)     # Off-white
    text_accent: Tuple[int, int, int] = (100, 220, 255)   # Cyan accent
    text_warning: Tuple[int, int, int] = (255, 200, 100)  # Orange/gold

    # Particle colors
    p_eat: Tuple[int, int, int] = (255, 220, 100)   # Gold burst on eating
    p_die: Tuple[int, int, int] = (255, 80, 80)     # Red explosion on death
    p_trail: Tuple[int, int, int] = (60, 180, 100)  # Ghost trail color

    @property
    def width(self) -> int:
        """Total pixel width of the game area."""
        return self.cell_size * self.grid_size

    @property
    def height(self) -> int:
        """Total pixel height of the game area."""
        return self.cell_size * self.grid_size


# ============================================================================
# HIGH SCORE PERSISTENCE
# ============================================================================

class ScoreManager:
    """
    Handles saving and loading high scores to disk.
    
    DEFENSIVE PROGRAMMING EXAMPLE:
    This class demonstrates how to handle file I/O safely:
    1. Check if file exists before reading
    2. Handle empty/corrupt files gracefully
    3. Validate data types after parsing
    4. Catch all reasonable exceptions
    5. Fail silently (return default) rather than crashing
    
    For a game, a corrupted save file should never crash the program.
    """
    
    def __init__(self, filepath: str = "vector_snake_scores.json"):
        """
        Initialize the score manager.
        
        Args:
            filepath: Where to save/load scores. Using JSON for human readability.
        """
        self.filepath = Path(filepath)
        self.highscore = self._load()

    def _load(self) -> int:
        """
        Load high score from disk with extensive error handling.
        
        Returns:
            The saved high score, or 0 if anything goes wrong.
        """
        # Guard 1: File doesn't exist yet (first run)
        if not self.filepath.exists():
            return 0

        try:
            # Guard 2: File exists but is empty (interrupted write)
            if self.filepath.stat().st_size == 0:
                return 0
            
            # Guard 3: File has content but it's whitespace only
            content = self.filepath.read_text()
            if not content.strip():
                return 0

            # Parse JSON
            data = json.loads(content)
            
            # Guard 4: JSON parsed but isn't a dict (e.g., just "123")
            if not isinstance(data, dict):
                return 0
            
            # Guard 5: Dict exists but highscore key is wrong type
            hs = data.get("highscore", 0)
            return int(hs) if isinstance(hs, (int, float)) else 0
            
        except (json.JSONDecodeError,    # Invalid JSON syntax
                OSError,                  # File read error
                UnicodeDecodeError,       # Binary/corrupt file
                ValueError,               # int() conversion failed
                AttributeError):          # None.get() or similar
            return 0

    def save(self, score: int) -> bool:
        """
        Save score if it's a new high score.
        
        Args:
            score: The score to potentially save
            
        Returns:
            True if this was a new high score, False otherwise
        """
        if score > self.highscore:
            self.highscore = score
            try:
                # Write atomically would be better (write to temp, then rename)
                # but for a simple game, this is sufficient
                self.filepath.write_text(json.dumps({"highscore": self.highscore}))
            except OSError:
                pass  # Silently fail - not critical
            return True
        return False


# ============================================================================
# PARTICLE SYSTEM
# ============================================================================

@dataclass
class Particle:
    """
    A single particle for visual effects (explosions, sparkles, etc.).
    
    PARTICLE SYSTEM BASICS:
    Particles are simple objects with position, velocity, and lifetime.
    Each frame, we:
    1. Move the particle (pos += vel * dt)
    2. Apply physics (friction, gravity)
    3. Age the particle (decrease lifetime)
    4. Remove dead particles
    
    This creates organic, dynamic effects cheaply - hundreds of simple
    objects are easier to render than complex animations.
    """
    pos: Vector2                      # Current position in pixels
    vel: Vector2                      # Velocity in pixels per second
    color: Tuple[int, int, int]       # RGB color
    life: float                       # Remaining life (1.0 = full, 0.0 = dead)
    decay: float                      # How fast life decreases per second
    size: float                       # Radius in pixels

    def update(self, dt: float) -> bool:
        """
        Update particle physics for one frame.
        
        Args:
            dt: Delta time in seconds since last frame
            
        Returns:
            True if particle is still alive, False if it should be removed
        """
        # Move based on velocity (basic kinematics: position += velocity * time)
        self.pos += self.vel * dt
        
        # Apply friction (multiply velocity by factor < 1 each frame)
        # This creates a natural deceleration without complex physics
        self.vel *= 0.92
        
        # Age the particle
        self.life -= self.decay * dt
        
        return self.life > 0


class ParticleSystem:
    """
    Manages a collection of particles with efficient batch operations.
    
    OPTIMIZATION TECHNIQUES DEMONSTRATED:
    
    1. Object Pooling (not implemented here, but mentioned):
       Instead of creating/destroying particles, reuse dead ones.
       Reduces garbage collection pressure.
    
    2. In-Place Filtering:
       Instead of `particles = [p for p in particles if p.alive]` which
       allocates a new list, we swap live particles to the front and
       truncate. This is O(n) with no allocation.
    
    3. Hybrid Rendering:
       Simple particles draw directly (fast). Complex alpha-blended
       particles use a cached surface (slower but prettier).
    """
    
    def __init__(self) -> None:
        self.particles: List[Particle] = []
        
        # Cache a surface for alpha-blended particle drawing
        # Creating surfaces is expensive; reusing is cheap
        self._particle_surf: Optional[pygame.Surface] = None
        self._max_particle_size = 12

    def _ensure_particle_surface(self) -> pygame.Surface:
        """Lazy-initialize and return the cached particle surface."""
        size = self._max_particle_size * 2
        if self._particle_surf is None or self._particle_surf.get_width() < size:
            # SRCALPHA flag enables per-pixel transparency
            self._particle_surf = pygame.Surface((size, size), pygame.SRCALPHA)
        return self._particle_surf

    def emit(
        self,
        pos: Vector2,
        color: Tuple[int, int, int],
        count: int = 10,
        speed: float = 100,
        size: float = 6,
    ) -> None:
        """
        Spawn a burst of particles at a position.
        
        This creates the classic "explosion" effect by spawning many particles
        with random velocities in all directions.
        
        Args:
            pos: Center point of the burst (in pixels)
            color: RGB color for all particles in this burst
            count: Number of particles to spawn
            speed: Maximum initial velocity (pixels/second)
            size: Maximum particle radius
        """
        for _ in range(count):
            # Random angle in radians (0 to 2π covers full circle)
            # math.tau = 2π ≈ 6.283
            angle = random.uniform(0.0, math.tau)
            
            # Random speed (30% to 100% of max for variety)
            spd = random.uniform(speed * 0.3, speed)
            
            # Convert polar (angle, speed) to cartesian (x, y) velocity
            vel = Vector2(math.cos(angle) * spd, math.sin(angle) * spd)
            
            self.particles.append(
                Particle(
                    pos=Vector2(pos),  # Copy to avoid aliasing
                    vel=vel,
                    color=color,
                    life=1.0,
                    decay=random.uniform(2.0, 4.0),  # Dies in 0.25-0.5 seconds
                    size=random.uniform(2.0, size),
                )
            )

    def update(self, dt: float) -> None:
        """
        Update all particles and remove dead ones.
        
        ALGORITHM: In-place partition (like quicksort's partition step)
        
        Instead of filtering to a new list:
            self.particles = [p for p in self.particles if p.update(dt)]
        
        We move live particles to the front and truncate:
            [live, live, dead, live, dead] → [live, live, live | truncate]
        
        This avoids allocating a new list every frame.
        """
        write_idx = 0
        for p in self.particles:
            if p.update(dt):
                # Particle is alive, keep it (may be writing to same position)
                self.particles[write_idx] = p
                write_idx += 1
        # Truncate dead particles from the end
        del self.particles[write_idx:]

    def draw(self, surface: pygame.Surface) -> None:
        """
        Render all particles to the surface.
        
        Uses two rendering paths:
        1. Fast path: Solid circles for bright/small particles
        2. Slow path: Alpha-blended circles for fading particles
        
        The slow path uses a cached surface because pygame.draw.circle()
        doesn't support alpha directly on non-SRCALPHA surfaces.
        """
        for p in self.particles:
            if p.life <= 0:
                continue

            # Scale size by remaining life (shrink as dying)
            sz = max(1, int(p.size * p.life))
            
            # Calculate alpha (transparency) from life
            alpha = int(255 * min(1.0, p.life))

            # Fast path: nearly opaque or tiny particles
            if alpha > 200 or sz <= 2:
                pygame.draw.circle(
                    surface, 
                    p.color[:3], 
                    (int(p.pos.x), int(p.pos.y)), 
                    sz
                )
            else:
                # Slow path: use intermediate surface for alpha blending
                ps = self._ensure_particle_surface()
                ps.fill((0, 0, 0, 0))  # Clear to transparent
                center = ps.get_width() // 2
                # Draw with alpha channel
                pygame.draw.circle(ps, (*p.color[:3], alpha), (center, center), sz)
                # Blit to main surface (alpha compositing happens here)
                surface.blit(ps, (int(p.pos.x) - center, int(p.pos.y) - center))


# ============================================================================
# SCREEN SHAKE
# ============================================================================

class ScreenShake:
    """
    Adds impact feedback by shaking the camera.
    
    GAME FEEL / "JUICE":
    Screen shake is one of the most effective ways to add impact to events.
    When the player dies or eats something, a brief shake makes it feel
    more significant. This is pure "juice" - no gameplay effect, all feel.
    
    IMPLEMENTATION:
    We track "trauma" which decays over time. The actual shake offset
    is trauma^2.5 (non-linear) so small trauma = tiny shake, but high
    trauma = dramatic shake. This prevents constant jittering while
    still allowing intense moments.
    """
    
    def __init__(self) -> None:
        self.offset = Vector2(0, 0)  # Current shake displacement
        self.trauma = 0.0            # Accumulated trauma (0-1)

    def add(self, amount: float) -> None:
        """
        Add trauma from an event. Capped at 1.0.
        
        Typical values:
        - 0.2: Minor event (eating fruit)
        - 0.5: Medium event (near miss)
        - 1.0: Major event (death)
        """
        self.trauma = min(1.0, self.trauma + amount)

    def update(self, dt: float) -> None:
        """
        Update shake offset and decay trauma.
        
        The key insight is using trauma^2.5 for the shake amount.
        This creates a non-linear response:
        - trauma=0.2 → shake=0.07 (barely noticeable)
        - trauma=0.5 → shake=0.18 (noticeable)
        - trauma=1.0 → shake=1.00 (intense)
        """
        if self.trauma > 0:
            # Non-linear falloff: low trauma = subtle, high trauma = intense
            shake = self.trauma ** 2.5
            
            # Convert shake intensity to pixel offset
            max_off = 12.0 * shake
            
            # Random offset each frame (creates the "shake" appearance)
            # random.random() returns [0, 1), we want [-1, 1)
            self.offset.x = (random.random() * 2.0 - 1.0) * max_off
            self.offset.y = (random.random() * 2.0 - 1.0) * max_off
            
            # Decay trauma over time
            self.trauma = max(0.0, self.trauma - 2.0 * dt)
        else:
            # No trauma = no offset
            self.offset.xy = 0, 0


# ============================================================================
# TRAIL SYSTEM (AFTERIMAGES)
# ============================================================================

class TrailSystem:
    """
    Creates ghost/afterimage effect showing previous snake positions.
    
    IMPLEMENTATION:
    We store a history of recent snake positions. Each frame, we draw
    older positions with increasing transparency, creating a "trail"
    effect that suggests motion.
    
    MEMORY OPTIMIZATION:
    We store positions as simple (x, y) tuples rather than Vector2 objects.
    For historical data we only read (never modify), tuples are more
    memory-efficient and slightly faster to iterate.
    """
    
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        # deque with maxlen automatically discards oldest entries
        # This is perfect for a sliding window of history
        self.history: Deque[List[Tuple[float, float]]] = deque(maxlen=cfg.trail_length)

    def record(self, body_deque: Deque[Vector2]) -> None:
        """
        Record current snake position for the trail.
        
        Called once per game tick (not per frame) to capture discrete positions.
        """
        # Convert Vector2s to tuples for lighter storage
        self.history.append([(p.x, p.y) for p in body_deque])

    def clear(self) -> None:
        """Clear trail history (e.g., on game restart)."""
        self.history.clear()

    def draw(self, surface: pygame.Surface) -> None:
        """
        Draw ghost trail of previous positions.
        
        Older positions are drawn more faintly, creating depth.
        """
        if not self.history:
            return

        cell = self.cfg.cell_size
        base_alpha = 80  # Starting opacity for newest trail segment

        for i, snapshot in enumerate(self.history):
            # Calculate fade based on age (older = more faded)
            # i=0 is oldest, i=len-1 is newest
            age_factor = (i + 1) / len(self.history)
            alpha = int(base_alpha * (1 - age_factor) * self.cfg.trail_alpha_decay)

            # Skip nearly invisible trails (optimization)
            if alpha < 5:
                continue

            # Draw each segment as a hollow rectangle
            for px, py in snapshot:
                rect = pygame.Rect(
                    int(px * cell) + 4,  # Inset from cell edges
                    int(py * cell) + 4,
                    cell - 8,
                    cell - 8,
                )
                # width=1 draws outline only (hollow rectangle)
                pygame.draw.rect(surface, self.cfg.p_trail, rect, width=1, border_radius=3)


# ============================================================================
# SNAKE ENTITY
# ============================================================================

class Snake:
    """
    The player-controlled snake.
    
    KEY CONCEPTS:
    
    1. INPUT BUFFERING:
       We queue up to 3 direction changes. This prevents frustration when
       the player presses two directions quickly (e.g., up then right to
       turn a corner). Without buffering, the second input would be lost.
    
    2. DEQUE FOR BODY:
       The snake body is a deque (double-ended queue) because we frequently
       add to the front (new head) and remove from the back (tail).
       - List: insert(0, x) is O(n), pop() is O(1)
       - Deque: appendleft(x) is O(1), pop() is O(1)
    
    3. VISUAL INTERPOLATION:
       The snake moves in discrete grid steps, but we interpolate the
       visual position between steps. This makes movement appear smooth
       even though the logic is grid-based.
    """
    
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        
        # Body is a deque of grid positions (not pixels)
        # Head is body[0], tail is body[-1]
        self.body: Deque[Vector2] = deque()
        
        # Current movement direction (unit vector)
        self.direction: Vector2 = Vector2(1, 0)
        
        # Input buffer: queued direction changes
        # maxlen=3 prevents excessive buffering
        self._input_queue: Deque[Vector2] = deque(maxlen=3)
        
        # Pending growth (segments to add)
        self._grow_pending: int = 0
        
        # Visual interpolation state
        self._visual_positions: List[Vector2] = []  # Positions at start of current tick
        self._lerp_t: float = 1.0                   # Interpolation progress (0=start, 1=end)
        
        self.reset()

    def reset(self) -> None:
        """Reset snake to starting state for new game."""
        # Start with 3 segments, moving right
        self.body = deque([Vector2(5, 10), Vector2(4, 10), Vector2(3, 10)])
        self.direction = Vector2(1, 0)
        self._input_queue.clear()
        self._grow_pending = 0
        self._visual_positions = [Vector2(p) for p in self.body]
        self._lerp_t = 1.0

    @property
    def head(self) -> Vector2:
        """Convenience property to access the head segment."""
        return self.body[0]

    def queue_turn(self, new_dir: Vector2) -> None:
        """
        Queue a direction change from player input.
        
        INPUT VALIDATION:
        - Ignore zero-length directions
        - Prevent 180° turns (instant self-collision)
        - Prevent duplicate consecutive directions
        
        The validation checks against the LAST QUEUED direction, not the
        current direction. This allows rapid corner turns like:
        current=RIGHT, queue=[UP, LEFT] which is valid (turns a corner)
        """
        if new_dir.length_squared() == 0:
            return
            
        # Check against last queued direction (or current if queue empty)
        last_dir = self._input_queue[-1] if self._input_queue else self.direction

        # Prevent 180° turn (new_dir == -last_dir means opposite direction)
        # Prevent redundant input (new_dir == last_dir)
        if new_dir == -last_dir or new_dir == last_dir:
            return
            
        self._input_queue.append(new_dir)

    def step(self) -> None:
        """
        Execute one movement tick.
        
        This is called at a fixed rate (e.g., every 120ms) regardless of
        frame rate. This ensures consistent game speed across different
        hardware.
        
        MOVEMENT ALGORITHM:
        1. Snapshot current positions for interpolation
        2. Apply next queued direction (if any)
        3. Create new head in movement direction
        4. Remove tail (unless growing)
        """
        # Snapshot current positions for smooth visual interpolation
        self._visual_positions = [Vector2(p) for p in self.body]
        self._lerp_t = 0.0  # Reset interpolation

        # Process input queue
        if self._input_queue:
            next_dir = self._input_queue.popleft()
            # Double-check 180° prevention (belt and suspenders)
            if next_dir != -self.direction:
                self.direction = next_dir

        # Calculate new head position
        new_head = self.head + self.direction
        
        # Add new head to front (O(1) with deque)
        self.body.appendleft(new_head)

        # Handle growth vs normal movement
        if self._grow_pending > 0:
            self._grow_pending -= 1
            # Don't remove tail; snake grows
            # Add extra visual position to prevent popping artifact
            if self._visual_positions:
                self._visual_positions.append(self._visual_positions[-1])
        else:
            # Remove tail to maintain length (O(1) with deque)
            self.body.pop()

    def grow(self, amount: int = 1) -> None:
        """Queue growth. The snake will grow by this many segments."""
        self._grow_pending += amount

    def update_visual(self, dt: float, move_ms: int) -> None:
        """
        Update visual interpolation progress.
        
        Called every frame (not just every tick) to smoothly animate
        between discrete grid positions.
        
        Args:
            dt: Frame time in seconds
            move_ms: Milliseconds between movement ticks
        """
        # How much of the tick interval this frame represents
        speed_factor = (dt * 1000.0) / move_ms
        self._lerp_t = min(1.0, self._lerp_t + speed_factor)

    def check_self_collision(self) -> bool:
        """
        Check if head overlaps any body segment.
        
        OPTIMIZATION:
        We use itertools.islice to skip the head (body[0]) without
        creating a copy of the list. For small snakes this doesn't
        matter, but it's good practice.
        
        Returns:
            True if snake has collided with itself
        """
        head_x, head_y = int(self.head.x), int(self.head.y)
        
        # Check each body segment (skip head at index 0)
        for segment in itertools.islice(self.body, 1, None):
            if int(segment.x) == head_x and int(segment.y) == head_y:
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        """
        Render the snake with interpolated positions and color gradient.
        
        VISUAL FEATURES:
        1. Position interpolation (smooth movement between grid cells)
        2. Color gradient from head to tail
        3. Connector lines between segments (vector aesthetic)
        4. Highlight effect on each segment
        """
        cell = self.cfg.cell_size
        
        # Convert deque to list for indexed access
        # (deque indexing is O(n), list is O(1))
        real_body_list = list(self.body)
        count = len(real_body_list)

        # Calculate interpolated render positions
        render_positions: List[Vector2] = []
        for i in range(count):
            if i < len(self._visual_positions):
                # Lerp from old position to new position
                pos = self._visual_positions[i].lerp(real_body_list[i], self._lerp_t)
            else:
                # New segment (from growth), no interpolation needed
                pos = real_body_list[i]
            render_positions.append(pos)

        # Draw connector lines between segments (vector aesthetic)
        # Must have at least 2 points for pygame.draw.lines()
        if len(render_positions) >= 2:
            # Convert grid coords to pixel coords (center of each cell)
            points = [
                (int((p.x + 0.5) * cell), int((p.y + 0.5) * cell)) 
                for p in render_positions
            ]
            pygame.draw.lines(surface, self.cfg.snake_connector, False, points, 2)

        # Draw each segment
        for i, pos in enumerate(render_positions):
            # Calculate gradient position (0 = head, 1 = tail)
            t = i / max(1, count - 1)

            # Head uses special color, body uses gradient
            if i == 0:
                color = self.cfg.snake_head
            else:
                color = lerp_color(self.cfg.snake_body, self.cfg.snake_tail, t)

            # Draw main segment rectangle
            rect = pygame.Rect(pos.x * cell, pos.y * cell, cell, cell)
            pygame.draw.rect(surface, color, rect, border_radius=5)

            # Draw highlight (glassy effect)
            inner = rect.inflate(-8, -8)
            if inner.w > 0 and inner.h > 0:
                pygame.draw.rect(surface, (220, 220, 230), inner, width=1, border_radius=3)


# ============================================================================
# FRUIT ENTITY
# ============================================================================

class Fruit:
    """
    The collectible fruit with animated visual effects.
    
    VISUAL DESIGN:
    Instead of a plain circle, we render:
    1. A soft glow (cached surface with alpha)
    2. An outer rotating diamond
    3. An inner counter-rotating diamond
    4. A center dot
    
    This creates an eye-catching, dynamic target that stands out
    against the grid background.
    """
    
    def __init__(self, pos: Vector2, cfg: Config) -> None:
        self.pos = pos
        self.cfg = cfg
        self.anim_timer = 0.0  # Drives pulse animation
        self.rotation = 0.0    # Current rotation angle

        # Pre-render glow surface (expensive, so cache it)
        # This avoids redrawing the glow every frame
        base_radius = cfg.cell_size // 2 - 2
        glow_radius = int(base_radius * 2.0)
        self._glow_radius = glow_radius
        self._glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            self._glow_surf,
            (*cfg.fruit_glow, 40),  # 40 alpha = subtle glow
            (glow_radius, glow_radius),
            glow_radius,
        )

    def update(self, dt: float) -> None:
        """Update animation timers."""
        self.anim_timer += dt * 4.0  # Controls pulse speed
        self.rotation += dt * 2.0    # Controls rotation speed

    def draw(self, surface: pygame.Surface) -> None:
        """Render the fruit with all its visual layers."""
        cfg = self.cfg
        
        # Calculate center position in pixels
        cx = int((self.pos.x + 0.5) * cfg.cell_size)
        cy = int((self.pos.y + 0.5) * cfg.cell_size)

        # Pulsing scale using sine wave (smooth oscillation)
        # sin() returns [-1, 1], so scale oscillates [0.85, 1.15]
        scale = 1.0 + 0.15 * math.sin(self.anim_timer)
        base_size = cfg.cell_size // 2 - 2

        # Layer 1: Glow (pre-rendered, just blit it)
        surface.blit(self._glow_surf, (cx - self._glow_radius, cy - self._glow_radius))

        # Layer 2: Outer diamond (rotating)
        outer_size = int(base_size * scale * 1.2)
        self._draw_diamond(surface, cx, cy, outer_size, self.rotation, cfg.fruit_outer)

        # Layer 3: Inner diamond (counter-rotating for visual interest)
        inner_size = int(base_size * scale * 0.7)
        self._draw_diamond(surface, cx, cy, inner_size, -self.rotation * 1.5, cfg.fruit_core)

        # Layer 4: Center dot
        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), 2)

    def _draw_diamond(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        size: int,
        angle: float,
        color: Tuple[int, int, int],
    ) -> None:
        """
        Draw a rotated diamond (square rotated 45°).
        
        MATH:
        A diamond is just 4 points arranged in a circle, spaced 90° apart.
        We use sin/cos to calculate each point's position from the center.
        """
        points = []
        for i in range(4):
            # 4 points, 90° (π/2 radians) apart
            a = angle + i * (math.pi / 2)
            px = cx + math.cos(a) * size
            py = cy + math.sin(a) * size
            points.append((px, py))
        # width=2 draws outline only
        pygame.draw.polygon(surface, color, points, width=2)


# ============================================================================
# VISUAL EFFECTS
# ============================================================================

class VisualEffects:
    """
    Post-processing visual effects: scanlines and vignette.
    
    DESIGN PHILOSOPHY:
    These effects are purely aesthetic ("juice") and don't affect gameplay.
    They add a retro/atmospheric feel but should be:
    1. Subtle (not distracting)
    2. Toggleable (accessibility)
    3. Efficient (rendered once, cached)
    
    SCANLINES: Horizontal dark lines every few pixels, mimicking CRT displays
    VIGNETTE: Darkening around screen edges, focuses attention on center
    """
    
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self._scanline_surf: Optional[pygame.Surface] = None
        self._vignette_surf: Optional[pygame.Surface] = None
        self.boost_pulse_timer = 0.0  # Drives vignette pulse when boosting

    def _ensure_scanlines(self, width: int, height: int) -> pygame.Surface:
        """
        Lazy-create scanline overlay surface.
        
        Creates horizontal lines every 4 pixels. The surface is cached
        and only recreated if dimensions change.
        """
        if self._scanline_surf is None or self._scanline_surf.get_size() != (width, height):
            self._scanline_surf = pygame.Surface((width, height), pygame.SRCALPHA)
            for y in range(0, height, 4):
                pygame.draw.line(
                    self._scanline_surf,
                    (0, 0, 0, self.cfg.scanline_alpha),
                    (0, y),
                    (width, y),
                )
        return self._scanline_surf

    def _ensure_vignette(self, width: int, height: int) -> pygame.Surface:
        """
        Lazy-create vignette overlay surface.
        
        OPTIMIZATION: Render at 1/4 resolution then upscale.
        
        A proper vignette requires calculating distance-from-center for
        every pixel, which is expensive. By rendering at lower resolution
        and using smoothscale, we get a visually similar result much faster.
        
        The vignette uses a power curve (normalized_distance ^ 2.5) to
        create a natural falloff that's subtle in the center and strong
        at the edges.
        """
        if self._vignette_surf is None or self._vignette_surf.get_size() != (width, height):
            # Render at 1/4 resolution
            w_small, h_small = width // 4, height // 4
            
            # Guard against zero-size surfaces
            if w_small == 0 or h_small == 0:
                self._vignette_surf = pygame.Surface((width, height), pygame.SRCALPHA)
                return self._vignette_surf

            temp_surf = pygame.Surface((w_small, h_small), pygame.SRCALPHA)
            cx, cy = w_small // 2, h_small // 2
            max_dist = math.sqrt(cx * cx + cy * cy) or 1.0  # Avoid division by zero

            # Calculate alpha for each pixel based on distance from center
            for y in range(h_small):
                for x in range(w_small):
                    dx, dy = x - cx, y - cy
                    dist = math.sqrt(dx * dx + dy * dy)
                    normalized = dist / max_dist  # 0 at center, 1 at corners
                    
                    # Power curve for natural falloff
                    alpha = int((normalized ** 2.5) * 180)
                    alpha = min(255, alpha)
                    
                    if alpha > 0:
                        temp_surf.set_at((x, y), (0, 0, 0, alpha))

            # Upscale to full resolution (smoothscale for anti-aliasing)
            self._vignette_surf = pygame.transform.smoothscale(temp_surf, (width, height))

        return self._vignette_surf

    def update(self, dt: float, is_boosting: bool) -> None:
        """Update effect timers."""
        if is_boosting:
            # Increase pulse timer while boosting
            self.boost_pulse_timer += dt * 8.0
        else:
            # Decay when not boosting
            self.boost_pulse_timer *= 0.9

    def draw_scanlines(self, surface: pygame.Surface) -> None:
        """Apply scanline effect if enabled."""
        if not self.cfg.scanlines_enabled:
            return
        scanlines = self._ensure_scanlines(surface.get_width(), surface.get_height())
        surface.blit(scanlines, (0, 0))

    def draw_vignette(self, surface: pygame.Surface, boost_intensity: float = 0.0) -> None:
        """
        Apply vignette effect with optional boost pulsing.
        
        When boosting, the vignette pulses darker/lighter using a sine wave,
        adding visual feedback for the speed boost state.
        """
        vignette = self._ensure_vignette(surface.get_width(), surface.get_height())
        
        # Calculate pulsing alpha
        pulse = math.sin(self.boost_pulse_timer) * 0.5 + 0.5  # Convert [-1,1] to [0,1]
        extra_alpha = int(self.cfg.vignette_boost_pulse_amount * pulse * boost_intensity)
        base_alpha = self.cfg.vignette_base_alpha + extra_alpha
        
        # Apply alpha and blit
        vignette.set_alpha(base_alpha)
        surface.blit(vignette, (0, 0))


# ============================================================================
# GAME STATE MACHINE
# ============================================================================

class GameState(Enum):
    """
    Possible states the game can be in.
    
    STATE MACHINE PATTERN:
    Instead of scattered boolean flags (is_playing, is_paused, is_dead),
    we use an enum to represent mutually exclusive states. This makes
    transitions explicit and prevents impossible states like
    "playing AND paused AND dead".
    
    State transitions:
        MENU → PLAYING (start game)
        PLAYING → PAUSED (press P)
        PLAYING → DYING (collision)
        PAUSED → PLAYING (press P)
        DYING → GAME_OVER (timer expires)
        GAME_OVER → PLAYING (restart)
    """
    MENU = auto()       # Title screen
    PLAYING = auto()    # Active gameplay
    PAUSED = auto()     # Gameplay suspended
    DYING = auto()      # Slow-motion death sequence
    GAME_OVER = auto()  # Final score screen


# ============================================================================
# GAME MANAGER
# ============================================================================

class Game:
    """
    Main game coordinator. Owns all game objects and manages state.
    
    RESPONSIBILITIES:
    - Initialize and reset game objects
    - Process input events
    - Update all systems each frame
    - Render all layers in correct order
    - Manage state transitions
    
    GAME LOOP ARCHITECTURE:
    This game uses a fixed timestep for logic with variable rendering.
    
    Logic (tick): Runs at fixed intervals (e.g., 120ms) regardless of frame rate.
                  This ensures consistent game speed and physics.
    
    Rendering: Runs as fast as possible, interpolating visual positions
               between logic ticks for smooth animation.
    
    Pseudocode:
        accumulator = 0
        while running:
            dt = time_since_last_frame()
            accumulator += dt
            
            while accumulator >= TICK_RATE:
                tick()  # Fixed timestep logic
                accumulator -= TICK_RATE
            
            lerp_t = accumulator / TICK_RATE
            draw(lerp_t)  # Interpolated rendering
    """
    
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        
        # === GAME OBJECTS ===
        self.snake = Snake(cfg)
        self.fruit = Fruit(Vector2(15, 15), cfg)
        
        # === STATE ===
        self.state = GameState.MENU
        
        # === EFFECTS ===
        self.particles = ParticleSystem()
        self.shake = ScreenShake()
        self.trail = TrailSystem(cfg)
        self.effects = VisualEffects(cfg)
        
        # === SCORING ===
        self.scores = ScoreManager()
        self.score = 0
        
        # === TIMING ===
        self.accum_time = 0      # Accumulated time for fixed timestep
        self.death_timer = 0.0   # Countdown during DYING state
        
        # === INPUT STATE ===
        self.is_boosting = False
        
        # === VISUAL STATE ===
        self.grid_intensity = 0.0  # Flash intensity when eating
        self.was_boosting_on_eat = False  # Track for UI feedback

        # === FONTS ===
        # Using system font (Consolas) for monospace/retro look
        self.font_big = pygame.font.SysFont("consolas", 60, bold=True)
        self.font_med = pygame.font.SysFont("consolas", 30)
        self.font_small = pygame.font.SysFont("consolas", 20)

        # === RENDER SURFACES ===
        # Main game surface (we render here, then blit to screen with shake)
        self.game_surf = pygame.Surface((cfg.width, cfg.height))
        
        # Pre-rendered grid surfaces (optimization: don't redraw lines every frame)
        self.grid_base_surf = self._build_grid_surface(cfg.grid_base)
        self.grid_active_surf = self._build_grid_surface(cfg.grid_active).convert_alpha()
        
        # FIX: Cache pause overlay instead of creating every frame
        self._pause_overlay: Optional[pygame.Surface] = None

    def _build_grid_surface(self, color: Tuple[int, int, int]) -> pygame.Surface:
        """Pre-render a grid surface with the given line color."""
        surf = pygame.Surface((self.cfg.width, self.cfg.height))
        surf.fill(self.cfg.bg)
        
        # Vertical lines
        for x in range(0, self.cfg.width, self.cfg.cell_size):
            pygame.draw.line(surf, color, (x, 0), (x, self.cfg.height))
            
        # Horizontal lines
        for y in range(0, self.cfg.height, self.cfg.cell_size):
            pygame.draw.line(surf, color, (0, y), (self.cfg.width, y))
            
        return surf

    def _ensure_pause_overlay(self) -> pygame.Surface:
        """Lazy-create pause overlay surface."""
        if self._pause_overlay is None:
            self._pause_overlay = pygame.Surface(
                (self.cfg.width, self.cfg.height), 
                pygame.SRCALPHA
            )
            self._pause_overlay.fill((0, 0, 0, 150))  # Semi-transparent black
        return self._pause_overlay

    def start(self) -> None:
        """Initialize/reset for a new game."""
        self.snake.reset()
        self.trail.clear()
        self.score = 0
        self.spawn_fruit()
        self.state = GameState.PLAYING
        self.accum_time = 0
        self.death_timer = 0.0
        self.is_boosting = False

    def spawn_fruit(self) -> None:
        """
        Place fruit in a random unoccupied cell.
        
        ALGORITHM CHOICE:
        We use two strategies depending on how full the grid is:
        
        1. Random sampling (fast when grid is mostly empty):
           Pick random cells until we find an empty one.
           Expected attempts ≈ 1/(1 - fill_ratio)
           
        2. Deterministic (guaranteed when grid is mostly full):
           Build list of all empty cells, pick one randomly.
           Always O(grid_size²) but guaranteed to work.
        
        We switch strategies at 50% fill ratio to balance speed and reliability.
        """
        # Build set of occupied positions
        occupied = {(int(p.x), int(p.y)) for p in self.snake.body}
        total_cells = self.cfg.grid_size * self.cfg.grid_size
        fill_ratio = len(occupied) / total_cells

        def deterministic_spawn() -> bool:
            """Build list of all free cells and pick one."""
            free_cells = [
                (x, y)
                for y in range(self.cfg.grid_size)
                for x in range(self.cfg.grid_size)
                if (x, y) not in occupied
            ]
            if not free_cells:
                return False  # Grid is completely full (player wins!)
            x, y = random.choice(free_cells)
            self.fruit = Fruit(Vector2(x, y), self.cfg)
            return True

        # Use deterministic method when grid is more than half full
        if fill_ratio >= 0.5:
            if not deterministic_spawn():
                self._trigger_death()  # Treat full grid as win/end
            return

        # Random sampling method (fast for sparse grids)
        max_attempts = 100
        for _ in range(max_attempts):
            x = random.randint(0, self.cfg.grid_size - 1)
            y = random.randint(0, self.cfg.grid_size - 1)
            if (x, y) not in occupied:
                self.fruit = Fruit(Vector2(x, y), self.cfg)
                return

        # Fallback to deterministic if random sampling fails
        # (statistically unlikely with fill_ratio < 0.5)
        if not deterministic_spawn():
            self._trigger_death()

    def handle_input(self, event: pygame.event.Event) -> None:
        """
        Process a single input event.
        
        INPUT HANDLING ARCHITECTURE:
        - Pygame gives us events (key presses, mouse clicks, etc.)
        - We handle them based on current game state
        - Some keys (ESC, F1) work in multiple states
        - Direction keys only work while PLAYING
        """
        if event.type == pygame.KEYDOWN:
            # === GLOBAL KEYS (work in any state) ===
            
            if event.key == pygame.K_ESCAPE:
                # ESC behavior depends on state
                if self.state == GameState.PLAYING:
                    self.state = GameState.PAUSED
                elif self.state == GameState.PAUSED:
                    self.state = GameState.PLAYING
                else:
                    # In menu or game over, ESC quits
                    pygame.quit()
                    sys.exit()

            if event.key == pygame.K_F1:
                # Toggle scanlines (accessibility option)
                self.cfg.scanlines_enabled = not self.cfg.scanlines_enabled

            # === MENU / GAME OVER KEYS ===
            
            if self.state in (GameState.MENU, GameState.GAME_OVER):
                if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.start()
                return  # Don't process other keys in these states

            # === PAUSED KEYS ===
            
            if self.state == GameState.PAUSED:
                if event.key == pygame.K_p:
                    self.state = GameState.PLAYING
                return

            # === PLAYING KEYS ===
            
            if self.state == GameState.PLAYING:
                if event.key == pygame.K_p:
                    self.state = GameState.PAUSED
                    return

                # Direction mapping (both WASD and arrows)
                dirs = {
                    pygame.K_UP: Vector2(0, -1),
                    pygame.K_w: Vector2(0, -1),
                    pygame.K_DOWN: Vector2(0, 1),
                    pygame.K_s: Vector2(0, 1),
                    pygame.K_LEFT: Vector2(-1, 0),
                    pygame.K_a: Vector2(-1, 0),
                    pygame.K_RIGHT: Vector2(1, 0),
                    pygame.K_d: Vector2(1, 0),
                }
                if event.key in dirs:
                    self.snake.queue_turn(dirs[event.key])

    def update(self, dt_ms: int) -> None:
        """
        Update game state for one frame.
        
        This is called every frame with the time since the last frame.
        We use this for:
        1. Reading held keys (boost)
        2. Updating visual effects (always, for smooth animations)
        3. Running game logic at fixed timestep (only while playing)
        
        Args:
            dt_ms: Milliseconds since last frame (from clock.tick())
        """
        dt = dt_ms / 1000.0  # Convert to seconds for physics calculations

        # === HELD KEY POLLING ===
        # Unlike events (pressed once), we poll for held keys every frame
        keys = pygame.key.get_pressed()
        self.is_boosting = (
            self.state == GameState.PLAYING
            and (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        )

        # === UPDATE EFFECTS (always, for smooth animations) ===
        self.particles.update(dt)
        self.shake.update(dt)
        self.fruit.update(dt)
        self.effects.update(dt, self.is_boosting)
        self.grid_intensity = max(0.0, self.grid_intensity - dt * 2.0)

        # === STATE-SPECIFIC UPDATES ===
        
        if self.state == GameState.PLAYING:
            # Update visual interpolation
            self.snake.update_visual(dt, self.current_tick_rate)
            # Run fixed-timestep game logic
            self._update_playing(dt_ms)

        elif self.state == GameState.DYING:
            # Slow-motion effect: update visuals at reduced speed
            slowmo_factor = 0.2
            self.snake.update_visual(dt * slowmo_factor, self.current_tick_rate)
            
            # Count down death timer
            self.death_timer -= dt
            if self.death_timer <= 0:
                self.state = GameState.GAME_OVER
                self.scores.save(self.score)

    def _update_playing(self, dt_ms: int) -> None:
        """
        Fixed timestep game logic update.
        
        FIXED TIMESTEP EXPLAINED:
        Instead of updating physics based on variable frame time, we
        accumulate time and run physics in fixed chunks. This ensures:
        
        1. Determinism: Same input = same result, regardless of frame rate
        2. Stability: Physics doesn't break at high/low frame rates
        3. Fairness: Game speed is consistent for all players
        
        The trade-off is potential "jitter" if tick rate doesn't divide
        evenly into frame rate, which we solve with visual interpolation.
        """
        self.accum_time += dt_ms
        tick_rate = self.current_tick_rate

        # Run as many ticks as accumulated time allows
        while self.accum_time >= tick_rate:
            self.accum_time -= tick_rate
            
            # Record position for trail BEFORE moving
            self.trail.record(self.snake.body)
            
            # Execute one game tick
            self.tick()
            
            # Stop if state changed (e.g., death)
            if self.state != GameState.PLAYING:
                break

    @property
    def current_tick_rate(self) -> int:
        """Get current movement speed in milliseconds per tick."""
        return self.cfg.boost_move_ms if self.is_boosting else self.cfg.base_move_ms

    def tick(self) -> None:
        """
        Execute one game logic tick.
        
        This is the core gameplay: move snake, check collisions, eat fruit.
        Called at fixed intervals (not every frame).
        """
        # Move snake one step
        self.snake.step()
        head = self.snake.head

        # === WALL COLLISION ===
        if not (0 <= head.x < self.cfg.grid_size and 0 <= head.y < self.cfg.grid_size):
            self._trigger_death()
            return

        # === SELF COLLISION ===
        if self.snake.check_self_collision():
            self._trigger_death()
            return

        # === FRUIT COLLISION ===
        if int(head.x) == int(self.fruit.pos.x) and int(head.y) == int(self.fruit.pos.y):
            self.eat_fruit()

    def eat_fruit(self) -> None:
        """Handle eating a fruit: score, grow, spawn new fruit, effects."""
        # Calculate score (with boost multiplier if applicable)
        points = self.cfg.base_score
        self.was_boosting_on_eat = self.is_boosting
        if self.is_boosting:
            points = int(points * self.cfg.boost_multiplier)
        self.score += points
        
        # Grow snake
        self.snake.grow()
        
        # Spawn new fruit
        self.spawn_fruit()
        
        # === JUICE (visual/audio feedback) ===
        
        # Particle burst at head position
        center = Vector2(
            (self.snake.head.x + 0.5) * self.cfg.cell_size,
            (self.snake.head.y + 0.5) * self.cfg.cell_size,
        )
        self.particles.emit(center, self.cfg.p_eat, count=15)
        
        # Screen shake
        self.shake.add(0.25)
        
        # Grid flash
        self.grid_intensity = 1.0

    def _trigger_death(self) -> None:
        """Handle collision: start death sequence."""
        self.state = GameState.DYING
        self.death_timer = self.cfg.death_slowdown_duration
        
        # Big shake
        self.shake.add(1.0)
        
        # Explosion at head
        head_px = Vector2(
            (self.snake.head.x + 0.5) * self.cfg.cell_size,
            (self.snake.head.y + 0.5) * self.cfg.cell_size,
        )
        self.particles.emit(head_px, self.cfg.p_die, count=40, speed=250, size=10)

    def draw(self, screen: pygame.Surface) -> None:
        """
        Render one frame.
        
        RENDERING ORDER (back to front):
        1. Background (solid color)
        2. Grid lines (base, then flash overlay)
        3. Trail (ghost positions)
        4. Fruit
        5. Snake
        6. Particles
        7. Post-processing (vignette, scanlines)
        8. UI text (not affected by shake)
        
        We render to game_surf first, then blit to screen with shake offset.
        UI is drawn directly to screen so it doesn't shake.
        """
        # === RENDER GAME WORLD TO INTERMEDIATE SURFACE ===
        
        # Clear with background color
        self.game_surf.fill(self.cfg.bg)
        
        # Draw base grid
        self.game_surf.blit(self.grid_base_surf, (0, 0))
        
        # Draw flashing grid overlay (when eating)
        if self.grid_intensity > 0.0:
            # FIX: Create a copy for alpha modification to avoid permanently
            # modifying the cached surface
            alpha = int(255 * min(1.0, self.grid_intensity))
            grid_copy = self.grid_active_surf.copy()
            grid_copy.set_alpha(alpha)
            self.game_surf.blit(grid_copy, (0, 0))

        # Draw game objects (only in relevant states)
        if self.state in (GameState.PLAYING, GameState.PAUSED, 
                         GameState.DYING, GameState.GAME_OVER):
            self.trail.draw(self.game_surf)
            self.fruit.draw(self.game_surf)
            self.snake.draw(self.game_surf)

        # Draw particles on top
        self.particles.draw(self.game_surf)

        # Apply post-processing effects
        boost_intensity = 1.0 if self.is_boosting else 0.0
        self.effects.draw_vignette(self.game_surf, boost_intensity)
        self.effects.draw_scanlines(self.game_surf)

        # === BLIT TO SCREEN WITH SHAKE ===
        screen.fill(self.cfg.bg)  # Clear screen (visible if shake moves game_surf)
        screen.blit(
            self.game_surf, 
            (int(self.shake.offset.x), int(self.shake.offset.y))
        )
        
        # === DRAW UI (no shake) ===
        self._draw_ui(screen)

    def _draw_ui(self, screen: pygame.Surface) -> None:
        """Draw UI elements based on current state."""
        
        if self.state == GameState.MENU:
            # Title screen
            self._draw_centered(screen, "VECTOR SNAKE", -60, self.font_big, self.cfg.text_accent)
            self._draw_centered(screen, "Press SPACE to Start", 0, self.font_med)
            self._draw_centered(screen, "WASD/Arrows: Move | Shift: Boost | P: Pause", 
                               40, self.font_small, (120, 120, 140))
            self._draw_centered(screen, "F1: Toggle Scanlines", 70, self.font_small, (100, 100, 120))
            
            if self.scores.highscore > 0:
                self._draw_centered(screen, f"High Score: {self.scores.highscore}", 
                                   -10, self.font_small, (150, 150, 170))

        elif self.state == GameState.PLAYING:
            # Score display
            score_txt = self.font_med.render(f"{self.score}", True, self.cfg.text_main)
            screen.blit(score_txt, (20, 20))
            
            # Boost indicator
            if self.is_boosting:
                boost_txt = self.font_small.render(">> BOOST x2 <<", True, self.cfg.text_warning)
                screen.blit(boost_txt, (20, 55))

        elif self.state == GameState.PAUSED:
            # Dim overlay (cached)
            screen.blit(self._ensure_pause_overlay(), (0, 0))
            
            # Pause text
            self._draw_centered(screen, "PAUSED", -20, self.font_big, self.cfg.text_accent)
            self._draw_centered(screen, "Press P or ESC to Resume", 30, self.font_med)

        elif self.state == GameState.DYING:
            # Simple "..." during death slowmo
            self._draw_centered(screen, "...", 0, self.font_big, self.cfg.p_die)

        elif self.state == GameState.GAME_OVER:
            # Game over screen
            self._draw_centered(screen, "CRASHED", -60, self.font_big, self.cfg.p_die)
            self._draw_centered(screen, f"Score: {self.score}", -10, self.font_med)
            
            if self.score == self.scores.highscore and self.score > 0:
                self._draw_centered(screen, "NEW HIGH SCORE!", 20, self.font_small, self.cfg.text_warning)
            else:
                self._draw_centered(screen, f"High Score: {self.scores.highscore}", 
                                   20, self.font_small, (150, 150, 150))
            
            self._draw_centered(screen, "Press SPACE to Restart", 70, self.font_small, self.cfg.text_accent)

    def _draw_centered(
        self,
        surf: pygame.Surface,
        text: str,
        offset_y: int,
        font: pygame.font.Font,
        color: Tuple[int, int, int] | None = None,
    ) -> None:
        """Helper to draw text centered on screen with vertical offset."""
        if color is None:
            color = self.cfg.text_main
        txt = font.render(text, True, color)
        rect = txt.get_rect(center=(self.cfg.width // 2, self.cfg.height // 2 + offset_y))
        surf.blit(txt, rect)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main() -> None:
    """
    Application entry point.
    
    This is the "game loop" - the fundamental structure of any real-time game:
    
    1. Initialize (pygame, window, game objects)
    2. Loop forever:
       a. Handle events (input)
       b. Update state (physics, AI, etc.)
       c. Render (draw everything)
       d. Wait (maintain target frame rate)
    3. Clean up (on exit)
    
    The clock.tick(fps) call both waits to maintain frame rate AND returns
    the actual time elapsed, which we pass to update() for physics.
    """
    # === INITIALIZATION ===
    pygame.init()
    
    cfg = Config()
    
    # Create window
    screen = pygame.display.set_mode((cfg.width, cfg.height))
    pygame.display.set_caption("Vector Snake 3.5")
    
    # Clock for frame timing
    clock = pygame.time.Clock()

    # Create game instance
    game = Game(cfg)

    # === MAIN LOOP ===
    while True:
        # Maintain target FPS and get actual frame time
        dt = clock.tick(cfg.fps)  # Returns milliseconds since last tick

        # Process all pending events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            game.handle_input(event)

        # Update game state
        game.update(dt)
        
        # Render
        game.draw(screen)
        
        # Flip display (show what we rendered)
        pygame.display.flip()


if __name__ == "__main__":
    main()
