from PIL import Image, ImageDraw
import random
import math

def generate_pencil_cover():
    """Generate algorithmic art cover for Pencil article"""
    
    # Canvas settings
    width, height = 800, 600
    seed = 12345
    random.seed(seed)
    
    # Create image with white background (paper color)
    img = Image.new('RGB', (width, height), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    
    # Parameters
    agent_count = 80
    noise_scale = 0.008
    max_steps = 300
    
    # Colors (Graphite grays and blue accent)
    colors = [
        (44, 62, 80),     # Dark graphite
        (52, 73, 94),     # Medium graphite
        (44, 62, 80),     # Light graphite
        (52, 152, 219),   # Blue accent
    ]
    
    # Generate agents
    agents = []
    for i in range(agent_count):
        agents.append({
            'x': random.uniform(0, width),
            'y': random.uniform(0, height),
            'vx': 0,
            'vy': 0,
            'life': random.randint(100, max_steps),
            'color': colors[i % len(colors)],
            'weight': random.uniform(0.5, 2.0)
        })
    
    # Simulate agents drawing
    for step in range(max_steps):
        for agent in agents:
            if agent['life'] <= 0:
                continue
            
            # Calculate Perlin noise-based direction
            nx = agent['x'] * noise_scale
            ny = agent['y'] * noise_scale
            nz = step * 0.01
            
            # Simple noise approximation using sine waves
            noise_val = (math.sin(nx * 3 + nz) + math.sin(ny * 2 + nz * 1.5)) / 2
            angle = noise_val * math.pi * 4
            
            # Update velocity
            agent['vx'] += math.cos(angle) * 0.3
            agent['vy'] += math.sin(angle) * 0.3
            
            # Dampen
            agent['vx'] *= 0.95
            agent['vy'] *= 0.95
            
            # Store previous position
            prev_x, prev_y = agent['x'], agent['y']
            
            # Update position
            agent['x'] += agent['vx'] * 2
            agent['y'] += agent['vy'] * 2
            
            # Boundary check
            if agent['x'] < 0 or agent['x'] > width:
                agent['vx'] *= -1
                agent['x'] = max(0, min(width, agent['x']))
            if agent['y'] < 0 or agent['y'] > height:
                agent['vy'] *= -1
                agent['y'] = max(0, min(height, agent['y']))
            
            # Draw line with varying opacity based on life
            opacity = int(150 * (agent['life'] / max_steps))
            color_with_alpha = (*agent['color'], opacity)
            
            # Draw the line
            draw.line([(prev_x, prev_y), (agent['x'], agent['y'])], 
                     fill=agent['color'], width=int(agent['weight']))
            
            # Decrease life
            agent['life'] -= 1
    
    # Add title text overlay
    # Note: PIL default font is basic, for production would use custom font
    
    # Save image
    img.save('Pencil_Algorithmic_Cover_800x600.png', 'PNG')
    print("[OK] PNG saved: Pencil_Algorithmic_Cover_800x600.png")
    print(f"  Dimensions: {width}x{height}")
    print(f"  Seed: {seed}")
    print(f"  Agents: {agent_count}")

if __name__ == "__main__":
    generate_pencil_cover()
