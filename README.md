# Vector Snake v3.5 - Educational Edition

A polished Snake game implementation demonstrating intermediate-to-advanced game development patterns in Python with Pygame. This project serves as a comprehensive learning resource for understanding professional game architecture, visual effects, and performance optimization.

![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)
![Pygame](https://img.shields.io/badge/pygame-2.0+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## 🎮 Features

### Gameplay
- **Classic Snake Mechanics** - Smooth, responsive grid-based movement
- **Boost Mode** - Hold Shift for 2x speed and 2x points (high risk/reward)
- **Smooth Controls** - Input buffering prevents missed commands
- **Dynamic Difficulty** - Game gets progressively faster as you grow

### Visual Effects
- **Neon Aesthetic** - Vector-style graphics with glowing elements
- **Particle Systems** - Explosions and bursts on eating/death
- **Screen Shake** - Impact feedback for game events
- **Ghost Trail** - Fading trail showing recent positions
- **Grid Flash** - Grid pulses when collecting fruit
- **Vignette Effect** - Dynamic edge darkening that intensifies when boosting
- **CRT Scanlines** - Optional retro scanline overlay (toggle with F1)

### Architecture Highlights
- **State Machine** - Clean separation of game states (Menu, Playing, Paused, Dying, Game Over)
- **Fixed Timestep** - Consistent physics regardless of frame rate
- **Component-Based Design** - Modular systems (Snake, Fruit, Particles, Effects)
- **Configuration Class** - Centralized tuning parameters
- **High Score Persistence** - Automatic save/load with defensive error handling

## 🚀 Quick Start

### Prerequisites
```bash
python >= 3.10
pygame >= 2.0.0
```

### Installation
```bash
# Clone the repository
git clone <your-repo-url>
cd vector-snake

# Install dependencies
pip install pygame

# Run the game
python vector_snake_v3_5_educational.py
```

## 🎯 Controls

| Input | Action |
|-------|--------|
| `WASD` / `Arrow Keys` | Move snake |
| `Shift` (hold) | Boost speed (2x points, higher risk) |
| `P` / `ESC` | Pause/Resume |
| `F1` | Toggle scanline effect |
| `Space` / `Enter` | Start game / Restart after game over |

## 📚 Educational Value

This codebase is designed to teach the following concepts:

### 1. Game Loop Architecture
```python
while True:
    dt = clock.tick(fps)      # Frame timing
    handle_events()            # Input processing
    update(dt)                 # Game state update
    draw()                     # Rendering
    flip()                     # Display update
```

The main loop demonstrates:
- Fixed timestep with delta time
- Separation of update and render phases
- Frame rate independence

### 2. State Machine Pattern
```python
class GameState(Enum):
    MENU = auto()
    PLAYING = auto()
    PAUSED = auto()
    DYING = auto()
    GAME_OVER = auto()
```

Game flow is managed through explicit states, preventing invalid transitions and making the game logic easier to reason about.

### 3. Particle Systems
The `ParticleSystem` class demonstrates:
- Object pooling for performance
- Physics simulation (velocity, gravity, friction)
- Alpha blending for visual depth
- Efficient batch rendering

### 4. Input Buffering
```python
class InputBuffer:
    def __init__(self, max_size: int = 3):
        self.buffer: Deque[Vector2] = deque(maxlen=max_size)
```

Prevents missed inputs during rapid key presses by queuing commands, making controls feel more responsive.

### 5. Visual Effects System
- **Screen Shake**: Pseudo-random decay for natural feel
- **Vignette**: Radial gradient darkening with boost pulsing
- **Trail System**: Ghost effect using interpolated colors
- **Grid Flash**: Smooth intensity decay

### 6. Performance Optimization
- **Surface Caching**: Pre-rendered grids and overlays
- **Dirty Rectangle**: Only update changed regions
- **Object Pooling**: Particle reuse
- **Batch Rendering**: Minimize draw calls

### 7. Configuration Management
All "magic numbers" are centralized in the `Config` dataclass:
```python
@dataclass
class Config:
    cell_size: int = 20
    grid_size: int = 30
    base_move_ms: int = 120
    # ... easily tunable parameters
```

### 8. Collision Detection
Two methods demonstrated:
- **Self-collision**: Set-based lookup for O(1) performance
- **Wall collision**: Boundary checking with grid coordinates

### 9. Color Math
```python
def lerp_color(c1, c2, t):
    """Linear interpolation between colors"""
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )
```

Used for smooth color transitions in trail effects and particles.

### 10. File I/O with Error Handling
The `ScoreManager` class demonstrates defensive programming:
```python
class ScoreManager:
    def load(self) -> int:
        try:
            # Attempt to load
        except FileNotFoundError:
            # Handle missing file
        except json.JSONDecodeError:
            # Handle corrupt file
        except Exception:
            # Catch-all for unexpected errors
```

## 🏗️ Architecture Overview

```
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
```

### Key Components

#### Game
Central coordinator that:
- Manages game state transitions
- Owns and updates all subsystems
- Handles timing and frame logic
- Coordinates rendering order

#### Snake
- Grid-based movement with fixed timestep
- Collision detection (self and walls)
- Gradient rendering (head → tail color transition)
- Connector lines between segments

#### Fruit
- Random spawn location (avoiding snake)
- Pulsing animation
- Glow effect rendering

#### ParticleSystem
- Spawns bursts of particles for events
- Physics simulation per particle
- Alpha fading over lifetime

#### EffectsManager
- Screen shake with decay
- Radial vignette overlay
- Optional scanline rendering

#### Trail
- Ring buffer of previous positions
- Fading ghost effect
- Color interpolation

## 🎨 Color Palette

The game uses a neon/vector aesthetic with carefully chosen colors:

```python
# Background
bg = (10, 10, 16)              # Near-black with blue tint

# Snake (gradient)
snake_head = (100, 255, 150)   # Bright green
snake_body = (50, 200, 100)    # Medium green
snake_tail = (30, 150, 80)     # Dark green

# Fruit
fruit_core = (255, 60, 100)    # Hot pink
fruit_outer = (255, 100, 150)  # Light pink

# UI
text_main = (240, 240, 250)    # Off-white
text_accent = (100, 220, 255)  # Cyan
text_warning = (255, 200, 100) # Gold/orange

# Particles
p_eat = (255, 220, 100)        # Gold burst
p_die = (255, 80, 80)          # Red explosion
p_trail = (60, 180, 100)       # Ghost green
```

## 🔧 Configuration & Tuning

All game parameters are exposed in the `Config` class for easy tweaking:

```python
cfg = Config()

# Adjust game speed
cfg.base_move_ms = 100  # Faster (lower = faster)
cfg.boost_move_ms = 40

# Tune visual effects
cfg.trail_length = 8
cfg.vignette_base_alpha = 60
cfg.scanlines_enabled = False

# Modify scoring
cfg.base_score = 10
cfg.boost_multiplier = 3.0
```

## 🐛 Bug Fixes in v3.5

This version addresses two important bugs:

1. **Pause Overlay Cache Bug**
   - **Problem**: Pause overlay was created every frame
   - **Fix**: Added `_pause_overlay` cache and `_ensure_pause_overlay()` method
   - **Impact**: Reduced CPU usage during pause state

2. **Grid Alpha Modification Bug**
   - **Problem**: Setting alpha on cached surface modified it permanently
   - **Fix**: Create a copy before alpha modification
   - **Impact**: Grid flash effect now works correctly on subsequent activations

## 📖 Code Reading Guide

For those learning from this codebase, suggested reading order:

1. **Start here**: `main()` function - understand the game loop
2. **Game flow**: `Game.__init__()` and `Game.update()` - see state management
3. **Core gameplay**: `Snake` class - movement and collision logic
4. **Visual effects**: `ParticleSystem` and `EffectsManager` classes
5. **Advanced**: `Trail` system and color interpolation
6. **Polish**: Input buffering and timing systems

Each section has extensive comments explaining **why** decisions were made, not just **what** the code does.

## 🎓 Learning Exercises

Try these modifications to deepen your understanding:

### Beginner
- [ ] Change the color palette
- [ ] Adjust movement speed and boost multiplier
- [ ] Modify particle count and behavior
- [ ] Add new visual effects (e.g., rotation on death)

### Intermediate
- [ ] Add power-ups (e.g., slow time, invincibility)
- [ ] Implement obstacles/walls on the grid
- [ ] Add sound effects
- [ ] Create multiple difficulty levels

### Advanced
- [ ] Add AI opponent snake
- [ ] Implement multiplayer (local or networked)
- [ ] Add procedurally generated mazes
- [ ] Create a replay system

## 📝 License

MIT License - Feel free to use this code for learning, teaching, or commercial projects.

## 🙏 Acknowledgments

This educational implementation builds on classic Snake game mechanics while demonstrating modern game development practices. The extensive documentation and clean architecture are intended to help developers at all levels understand professional game development patterns.

## 📞 Contributing

This is an educational project. If you find bugs, have suggestions for better explanations, or want to add educational features, contributions are welcome!

---

**Happy coding! 🐍**
