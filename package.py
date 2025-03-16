#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import zipfile
import shutil
import configparser

def get_addon_info():
    config = configparser.ConfigParser()
    config.read("addon/manifest.ini")
    
    # Get addon name and version from manifest
    try:
        name = config.get("addon", "name").replace(" ", "_").lower()
        version = config.get("addon", "version")
    except (configparser.NoSectionError, configparser.NoOptionError):
        # Fallback if config parsing fails
        name = "translator_gpt"
        version = "1.0"
    
    return name, version

def create_addon_package():
    addon_name, addon_version = get_addon_info()
    addon_file = f"{addon_name}-{addon_version}.nvda-addon"
    
    # Remove old build directory if exists
    if os.path.exists("build"):
        shutil.rmtree("build")
    
    # Create build directory
    os.makedirs("build", exist_ok=True)
    
    # Create a temporary directory for the addon files
    temp_dir = os.path.join("build", "temp")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    # Copy all files from addon directory to temp directory
    for root, dirs, files in os.walk("addon"):
        for file in files:
            src_path = os.path.join(root, file)
            # Get the relative path from addon directory
            rel_path = os.path.relpath(src_path, "addon")
            # Create the destination path
            dst_path = os.path.join(temp_dir, rel_path)
            # Create directories if they don't exist
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            # Copy the file
            shutil.copy2(src_path, dst_path)
    
    # Create addon zip file
    with zipfile.ZipFile(os.path.join("build", addon_file), "w") as addon_zip:
        # Add all files from temp directory
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Get the relative path from temp directory
                archive_path = os.path.relpath(file_path, temp_dir).replace("\\", "/")
                addon_zip.write(file_path, archive_path)
    
    # Clean up temp directory
    shutil.rmtree(temp_dir)
    
    print(f"Addon package created: build/{addon_file}")

if __name__ == "__main__":
    create_addon_package() 