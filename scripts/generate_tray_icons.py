"""scripts/generate_tray_icons.py — Utility to generate status icons for the System Tray.

Reads the main application logo and generates 4 distinct PNGs with status indicator
badges (Ready, Recording, Transcribing, Error) for the system tray applet.
"""

from pathlib import Path
from PIL import Image, ImageDraw

def generate_icons():
    project_root = Path(__file__).resolve().parent.parent
    logo_path = project_root / "assets" / "assist_transcribe_1x1.png"
    output_dir = project_root / "electron" / "assets"
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Try to load base logo, fallback to empty transparent image
    base_logo = None
    if logo_path.exists():
        try:
            base_logo = Image.open(logo_path).resize((32, 32), Image.Resampling.LANCZOS)
        except Exception as e:
            print(f"Warning: Failed to load app logo: {e}")
            
    states = {
        "idle": {"color": (120, 130, 140), "use_logo": True, "badge": False},
        "recording": {"color": (239, 91, 91), "use_logo": True, "badge": True},
        "transcribing": {"color": (250, 204, 21), "use_logo": True, "badge": True},
        "error": {"color": (220, 38, 38), "use_logo": True, "badge": True}
    }
    
    for name, conf in states.items():
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        if base_logo and name == "idle":
            # For idle, convert logo to grayscale/desaturated or keep it clean
            img = base_logo.copy()
            # Let's apply a slight opacity or desaturate it to show it's inactive
            r, g, b, a = img.split()
            # Make it slightly gray/semitransparent for idle state
            a = a.point(lambda p: int(p * 0.7))
            img = Image.merge("RGBA", (r, g, b, a))
        elif base_logo and conf["badge"]:
            img = base_logo.copy()
            draw_badge = ImageDraw.Draw(img)
            # Draw white border around badge
            draw_badge.ellipse((18, 18, 32, 32), fill=(255, 255, 255))
            # Draw inner color badge
            draw_badge.ellipse((20, 20, 30, 30), fill=conf["color"])
            
            if name == "error":
                # Draw white exclamation mark
                draw_badge.rectangle((24, 22, 26, 26), fill=(255, 255, 255))
                draw_badge.rectangle((24, 28, 26, 29), fill=(255, 255, 255))
        else:
            # Fallback when logo is missing
            draw.ellipse((4, 4, 28, 28), fill=conf["color"])
            draw.ellipse((2, 2, 30, 30), outline=(255, 255, 255), width=1)
            if name == "error":
                draw.rectangle((15, 8, 17, 20), fill=(255, 255, 255))
                draw.rectangle((15, 22, 17, 24), fill=(255, 255, 255))
                
        output_path = output_dir / f"tray_{name}.png"
        img.save(output_path, "PNG")
        print(f"Generated tray icon: {output_path}")

if __name__ == "__main__":
    generate_icons()
