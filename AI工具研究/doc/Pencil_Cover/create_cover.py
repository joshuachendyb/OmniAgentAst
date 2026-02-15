#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pencil Blueprint Clarity Cover - Museum Quality
Design Philosophy: Blueprint Clarity
Tool: Pencil Installation Research
"""

import warnings
warnings.filterwarnings('ignore')

import cairo
import math

# Canvas setup
WIDTH, HEIGHT = 800, 600
BG_COLOR = (0.97, 0.97, 0.95)  # Warm paper white
GRID_COLOR = (0.85, 0.87, 0.89)  # Subtle blueprint grid
LINE_COLOR = (0.25, 0.42, 0.55)  # Blueprint blue
ACCENT_COLOR = (0.95, 0.55, 0.25)  # Warm orange accent
TEXT_COLOR = (0.15, 0.20, 0.25)  # Deep charcoal

def create_pencil_blueprint_cover():
    # Create surface
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
    ctx = cairo.Context(surface)
    
    # 1. Background - Warm paper texture with subtle gradient
    ctx.set_source_rgb(*BG_COLOR)
    ctx.paint()
    
    # Subtle radial gradient from center
    gradient = cairo.RadialGradient(WIDTH/2, HEIGHT/2, 0, WIDTH/2, HEIGHT/2, 400)
    gradient.add_color_stop_rgba(0, 1.0, 1.0, 0.98, 0.3)
    gradient.add_color_stop_rgba(1, 0.97, 0.97, 0.95, 0.0)
    ctx.set_source(gradient)
    ctx.paint()
    
    # 2. Modular Grid System - Architectural blueprint aesthetic
    ctx.set_line_width(0.5)
    ctx.set_source_rgba(*GRID_COLOR[:3], 0.4)
    
    # Vertical modular lines
    for x in range(50, WIDTH, 40):
        ctx.move_to(x, 0)
        ctx.line_to(x, HEIGHT)
        ctx.stroke()
    
    # Horizontal modular lines
    for y in range(50, HEIGHT, 40):
        ctx.move_to(0, y)
        ctx.line_to(WIDTH, y)
        ctx.stroke()
    
    # 3. Geometric Construction Lines - Tool installation metaphor
    ctx.set_line_width(1.5)
    ctx.set_source_rgb(*LINE_COLOR)
    
    # Main construction frame (precision tool)
    ctx.set_line_join(cairo.LINE_JOIN_MITER)
    margin = 80
    ctx.rectangle(margin, margin, WIDTH - 2*margin, HEIGHT - 2*margin)
    ctx.stroke()
    
    # Diagonal construction lines - representing installation process flow
    ctx.set_line_width(0.8)
    ctx.set_dash([5, 3])
    ctx.move_to(margin, margin)
    ctx.line_to(WIDTH - margin, HEIGHT - margin)
    ctx.move_to(WIDTH - margin, margin)
    ctx.line_to(margin, HEIGHT - margin)
    ctx.stroke()
    ctx.set_dash([])
    
    # 4. Modular Blocks - Pencil's building blocks metaphor
    ctx.set_line_width(2)
    
    # Left modular cluster
    ctx.set_source_rgba(*LINE_COLOR[:3], 0.6)
    ctx.rectangle(120, 180, 60, 40)
    ctx.stroke()
    ctx.rectangle(130, 225, 40, 30)
    ctx.stroke()
    
    # Right modular cluster
    ctx.rectangle(WIDTH - 180, 160, 50, 50)
    ctx.stroke()
    ctx.rectangle(WIDTH - 170, 215, 35, 35)
    ctx.stroke()
    
    # 5. Central focal point - Tool essence
    center_x, center_y = WIDTH / 2, HEIGHT / 2 - 30
    
    # Concentric circles - precision tool core
    ctx.set_line_width(2.5)
    ctx.set_source_rgb(*LINE_COLOR)
    for r in [60, 50, 40, 30]:
        ctx.arc(center_x, center_y, r, 0, 2 * math.pi)
        ctx.stroke()
    
    # Center dot - installation completion point
    ctx.set_source_rgb(*ACCENT_COLOR)
    ctx.arc(center_x, center_y, 8, 0, 2 * math.pi)
    ctx.fill()
    
    # 6. Geometric shapes - Precision and clarity
    ctx.set_line_width(1.5)
    ctx.set_source_rgba(*LINE_COLOR[:3], 0.5)
    
    # Triangle precision marker (top)
    ctx.move_to(center_x, center_y - 90)
    ctx.line_to(center_x - 15, center_y - 65)
    ctx.line_to(center_x + 15, center_y - 65)
    ctx.close_path()
    ctx.stroke()
    
    # Rectangle module (bottom)
    ctx.rectangle(center_x - 20, center_y + 70, 40, 25)
    ctx.stroke()
    
    # 7. Title - Rare, powerful gesture (Blueprint Clarity)
    ctx.select_font_face("Helvetica", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    
    # Main title - "PENCIL"
    ctx.set_font_size(48)
    ctx.set_source_rgb(*TEXT_COLOR)
    text = "PENCIL"
    extents = ctx.text_extents(text)
    ctx.move_to(center_x - extents.width/2, 480)
    ctx.show_text(text)
    
    # Subtitle - minimal, precise
    ctx.set_font_size(14)
    ctx.select_font_face("Helvetica", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_source_rgba(*TEXT_COLOR[:3], 0.7)
    subtitle = "Installation Research"
    extents = ctx.text_extents(subtitle)
    ctx.move_to(center_x - extents.width/2, 515)
    ctx.show_text(subtitle)
    
    # Tool identifier - small, clinical
    ctx.set_font_size(10)
    ctx.set_source_rgba(*ACCENT_COLOR[:3], 0.8)
    label = "PROTOTYPE TOOL"
    extents = ctx.text_extents(label)
    ctx.move_to(center_x - extents.width/2, 535)
    ctx.show_text(label)
    
    # 8. Corner accents - Architectural precision
    ctx.set_line_width(2)
    ctx.set_source_rgba(*ACCENT_COLOR[:3], 0.6)
    
    corner_size = 25
    # Top-left corner
    ctx.move_to(margin + 10, margin + 10 + corner_size)
    ctx.line_to(margin + 10, margin + 10)
    ctx.line_to(margin + 10 + corner_size, margin + 10)
    ctx.stroke()
    
    # Bottom-right corner
    ctx.move_to(WIDTH - margin - 10, HEIGHT - margin - 10 - corner_size)
    ctx.line_to(WIDTH - margin - 10, HEIGHT - margin - 10)
    ctx.line_to(WIDTH - margin - 10 - corner_size, HEIGHT - margin - 10)
    ctx.stroke()
    
    # 9. Measurement marks - Scientific documentation aesthetic
    ctx.set_line_width(1)
    ctx.set_source_rgba(*LINE_COLOR[:3], 0.4)
    
    for i in range(5):
        x = margin + 100 + i * 120
        ctx.move_to(x, margin - 5)
        ctx.line_to(x, margin + 5)
        ctx.stroke()
    
    # Save
    surface.write_to_png('Pencil_Blueprint_Cover.png')
    print("Created: Pencil_Blueprint_Cover.png (800x600)")

if __name__ == '__main__':
    create_pencil_blueprint_cover()
