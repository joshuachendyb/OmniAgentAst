#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pencil Cover Design - Systematic Integration Philosophy
Canvas-design implementation using matplotlib + pycairo
"""

import warnings
warnings.filterwarnings('ignore')

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle, Polygon
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cairo

# Design parameters based on "Systematic Integration" philosophy
WIDTH = 1920
HEIGHT = 1080
DPI = 300

# Color palette - Technical environment
COLORS = {
    'deep_navy': '#0F172A',      # Terminal/code editor background
    'electric_cyan': '#06B6D4',  # Active connections, data flow
    'warm_amber': '#F59E0B',     # Human warmth
    'soft_gray': '#64748B',      # Technical documentation
    'grid_blue': '#1E3A5F',      # Grid lines
    'white': '#F8FAFC',          # Primary text
    'accent_cyan': '#22D3EE',    # Highlights
}

def create_pencil_cover():
    """Create cover based on Systematic Integration philosophy"""
    
    # Create figure with high resolution
    fig_width = WIDTH / DPI
    fig_height = HEIGHT / DPI
    fig, ax = plt.subplots(1, 1, figsize=(fig_width, fig_height), dpi=DPI)
    
    # Deep navy background - terminal aesthetic
    fig.patch.set_facecolor(COLORS['deep_navy'])
    ax.set_facecolor(COLORS['deep_navy'])
    ax.set_xlim(0, WIDTH)
    ax.set_ylim(0, HEIGHT)
    ax.axis('off')
    
    # Create systematic grid - architectural precision
    grid_spacing = 80
    for x in range(0, WIDTH, grid_spacing):
        ax.axvline(x=x, color=COLORS['grid_blue'], linewidth=0.5, alpha=0.3)
    for y in range(0, HEIGHT, grid_spacing):
        ax.axhline(y=y, color=COLORS['grid_blue'], linewidth=0.5, alpha=0.3)
    
    # Add connection points at grid intersections - MCP protocol visualization
    for x in range(0, WIDTH, grid_spacing*2):
        for y in range(0, HEIGHT, grid_spacing*2):
            circle = Circle((x, y), 3, color=COLORS['electric_cyan'], alpha=0.4)
            ax.add_patch(circle)
    
    # Title area - architectural blueprint style
    title_y = HEIGHT * 0.72
    subtitle_y = HEIGHT * 0.62
    
    # Main title - large, commanding
    ax.text(WIDTH/2, title_y, 'PENCIL',
            fontsize=120, fontweight='bold',
            ha='center', va='center',
            color=COLORS['white'],
            family='sans-serif')
    
    # Installation Study - secondary information
    ax.text(WIDTH/2, subtitle_y, 'Installation Research & Integration Guide',
            fontsize=32,
            ha='center', va='center',
            color=COLORS['electric_cyan'],
            family='sans-serif')
    
    # Technical details - systematic markers
    detail_y = HEIGHT * 0.45
    ax.text(WIDTH/2, detail_y, 
            'VS Code Extension • MCP Protocol • Windows Environment',
            fontsize=20,
            ha='center', va='center',
            color=COLORS['soft_gray'],
            family='sans-serif')
    
    # Connection lines - invisible connections made visible
    # Vertical line representing integration flow
    line_x = WIDTH * 0.15
    ax.plot([line_x, line_x], [HEIGHT*0.2, HEIGHT*0.8],
            '-', color=COLORS['electric_cyan'], linewidth=2, alpha=0.6)
    
    # Horizontal connection markers
    for y in [HEIGHT*0.3, HEIGHT*0.5, HEIGHT*0.7]:
        ax.plot([line_x-10, line_x+10], [y, y],
                '-', color=COLORS['electric_cyan'], linewidth=2)
    
    # Right side - geometric accent (MCP visualization)
    center_x = WIDTH * 0.85
    center_y = HEIGHT * 0.25
    
    # Concentric circles - protocol layers
    for r in [60, 80, 100, 120]:
        circle = Circle((center_x, center_y), r, 
                       fill=False, 
                       edgecolor=COLORS['electric_cyan'], 
                       linewidth=1.5, alpha=0.5)
        ax.add_patch(circle)
    
    # Central node
    circle = Circle((center_x, center_y), 15, 
                   color=COLORS['accent_cyan'], alpha=0.9)
    ax.add_patch(circle)
    
    # Connection line from title to node
    ax.plot([WIDTH*0.65, center_x-120], [HEIGHT*0.62, center_y],
            '--', color=COLORS['warm_amber'], linewidth=1.5, alpha=0.6)
    
    # Bottom information bar
    bar_y = HEIGHT * 0.12
    ax.text(WIDTH*0.5, bar_y, 
            'Version 1.0  •  February 2026  •  Technical Documentation',
            fontsize=14,
            ha='center', va='center',
            color=COLORS['soft_gray'],
            family='sans-serif')
    
    # Decorative corner elements - architectural precision
    corner_size = 100
    # Top left
    ax.plot([0, corner_size], [HEIGHT, HEIGHT], 
            '-', color=COLORS['electric_cyan'], linewidth=3)
    ax.plot([0, 0], [HEIGHT-corner_size, HEIGHT], 
            '-', color=COLORS['electric_cyan'], linewidth=3)
    
    # Bottom right
    ax.plot([WIDTH-corner_size, WIDTH], [0, 0], 
            '-', color=COLORS['electric_cyan'], linewidth=3)
    ax.plot([WIDTH, WIDTH], [0, corner_size], 
            '-', color=COLORS['electric_cyan'], linewidth=3)
    
    # Save with high quality
    output_path = 'Pencil_Cover_Systematic_Integration.png'
    fig.savefig(output_path, dpi=DPI, 
                facecolor=COLORS['deep_navy'],
                edgecolor='none',
                bbox_inches=None,
                pad_inches=0)
    plt.close(fig)
    
    print(f"Cover generated: {output_path}")
    print(f"Dimensions: {WIDTH}x{HEIGHT}, DPI: {DPI}")

if __name__ == '__main__':
    create_pencil_cover()
