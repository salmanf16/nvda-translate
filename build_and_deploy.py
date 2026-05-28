# -*- coding: utf-8 -*-
import os
import shutil
import zipfile

SRC_DIR = r"d:\Translate"
INSTALL_DIR = r"C:\Users\salma\AppData\Roaming\nvda\addons\translate"
OUTPUT_ADDON = r"d:\translate.nvda-addon"

EXCLUDE_DIRS = {"__pycache__", ".git", "libs", "translateDependencies", "translateModels"}
EXCLUDE_EXTS = {".pyc", ".whl", ".zip", ".nvda-addon", ".gitattributes", ".gitignore"}


def clean_pycache(directory):
	if not os.path.exists(directory):
		return
	for root, dirs, files in os.walk(directory):
		for d in list(dirs):
			if d == "__pycache__":
				path = os.path.join(root, d)
				try:
					shutil.rmtree(path)
					dirs.remove(d)
				except Exception:
					pass


def should_exclude(f, relative_path):
	f_lower = f.lower()
	if f_lower == "manifest.ini":
		return False
	ext = os.path.splitext(f)[1].lower()
	if ext in EXCLUDE_EXTS or ext in (".ini", ".json", ".log", ".txt"):
		return True
	if relative_path == "." and ext == ".py":
		return True
	return False


def copy_to_installed():
	clean_pycache(SRC_DIR)
	clean_pycache(INSTALL_DIR)
	print("Copying project files to installed NVDA addon folder...")
	if not os.path.exists(INSTALL_DIR):
		print(f"Error: Installed directory {INSTALL_DIR} does not exist!")
		return False

	copied_count = 0
	for root, dirs, files in os.walk(SRC_DIR):
		# Modify dirs in-place to skip excluded directories
		dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

		relative_path = os.path.relpath(root, SRC_DIR)
		if relative_path == ".":
			target_root = INSTALL_DIR
		else:
			target_root = os.path.join(INSTALL_DIR, relative_path)

		os.makedirs(target_root, exist_ok=True)

		for f in files:
			if should_exclude(f, relative_path):
				continue

			src_file = os.path.join(root, f)
			dst_file = os.path.join(target_root, f)
			
			shutil.copy2(src_file, dst_file)
			copied_count += 1

	print(f"Successfully copied {copied_count} files to NVDA installation.")
	return True


def package_addon():
	clean_pycache(SRC_DIR)
	print(f"Packaging addon into {OUTPUT_ADDON}...")
	
	try:
		if os.path.exists(OUTPUT_ADDON):
			os.remove(OUTPUT_ADDON)
	except Exception as e:
		print(f"Error removing old addon file: {e}")
		return False

	packed_count = 0
	with zipfile.ZipFile(OUTPUT_ADDON, "w", zipfile.ZIP_DEFLATED) as zf:
		for root, dirs, files in os.walk(SRC_DIR):
			dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
			
			relative_path = os.path.relpath(root, SRC_DIR)
			
			for f in files:
				if should_exclude(f, relative_path):
					continue

				file_path = os.path.join(root, f)
				
				if relative_path == ".":
					arcname = f
				else:
					arcname = os.path.join(relative_path, f)
					
				zf.write(file_path, arcname)
				packed_count += 1

	print(f"Successfully packaged {packed_count} files into {OUTPUT_ADDON}.")
	return True


if __name__ == "__main__":
	print("--- NVDA Translate Addon Deploy & Package ---")
	copy_success = copy_to_installed()
	pkg_success = package_addon()
	if copy_success and pkg_success:
		print("Deployment and packaging completed successfully!")
	else:
		print("Process completed with errors.")
