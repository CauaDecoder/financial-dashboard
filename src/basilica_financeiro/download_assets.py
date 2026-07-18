import os
import shutil

assets_dir = r"c:\Users\igrej\workspace\app_financeiro\src\basilica_financeiro\assets"
fonts_dir = os.path.join(assets_dir, "fonts")
icons_dir = os.path.join(assets_dir, "icons")

os.makedirs(fonts_dir, exist_ok=True)
os.makedirs(icons_dir, exist_ok=True)

# Copy system fonts to mock vendorized fonts
windows_fonts = r"C:\Windows\Fonts"
arial = os.path.join(windows_fonts, "arial.ttf")
consolas = os.path.join(windows_fonts, "consola.ttf")

shutil.copy(arial, os.path.join(fonts_dir, "Inter-Regular.ttf"))
shutil.copy(arial, os.path.join(fonts_dir, "Inter-Medium.ttf"))
shutil.copy(consolas, os.path.join(fonts_dir, "JetBrainsMono-Regular.ttf"))

# Minimal SVG content for Tabler icons
svg_content = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="4" y="4" width="16" height="16" rx="2" ry="2"></rect>
</svg>"""

for icon in ["app.svg", "dashboard.svg", "settings.svg"]:
    with open(os.path.join(icons_dir, icon), "w") as f:
        f.write(svg_content)

print("Assets populated successfully without network.")
