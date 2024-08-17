import os
import shutil
from urllib.request import urlretrieve

def pre_build_hook(ctx):
    print("Downloading SDL2_image dependencies...")
    url = "https://www.libsdl.org/projects/SDL_image/release/SDL2_image-2.0.5.zip"
    filename = os.path.join(ctx.build_dir, "SDL2_image-2.0.5.zip")
    urlretrieve(url, filename)
    shutil.unpack_archive(filename, ctx.build_dir)