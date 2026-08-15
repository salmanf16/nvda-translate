# -*- coding: utf-8 -*-
import os
import shutil
import zipfile
import subprocess

SRC_DIR = r"d:\Translate"
INSTALL_DIR = r"C:\Users\salma\AppData\Roaming\nvda\addons\translate"
OUTPUT_ADDON = r"d:\translate.nvda-addon"


def compile_locales():
	"""Ensures all gettext .po files are compiled into .mo binary catalogs before packaging."""
	msgfmt_script = os.path.join(SRC_DIR, "translate_all_locales.py")
	if os.path.exists(msgfmt_script):
		print("Compiling gettext catalogs (.po -> .mo)...")
		try:
			subprocess.run(["python", msgfmt_script], cwd=SRC_DIR, capture_output=True, check=True)
		except Exception as e:
			print(f"Warning: Could not auto-compile catalogs: {e}")


def get_whitelisted_addon_files():
	"""
	Strict Whitelist: Returns exact list of (src_absolute_path, relative_addon_path)
	that truly belong in the NVDA Translate addon.
	
	Strictly excludes:
	- All development scripts (*.py at root, test suites, build scripts)
	- Git files and metadata (.git, .gitignore, .gitattributes)
	- GitHub and repo documents (README.md, LICENSE, issue templates)
	- Source gettext files (*.po)
	- Bytecode cache (__pycache__, *.pyc)
	- Development logs and temp files (*.log, *.json, *.tmp)
	"""
	files_to_include = []

	# 1. Root Manifest
	root_manifest = os.path.join(SRC_DIR, "manifest.ini")
	if os.path.exists(root_manifest):
		files_to_include.append((root_manifest, "manifest.ini"))

	# 2. globalPlugins/translate/ code
	plugins_dir = os.path.join(SRC_DIR, "globalPlugins", "translate")
	if os.path.exists(plugins_dir):
		for root, dirs, files in os.walk(plugins_dir):
			if "__pycache__" in dirs:
				dirs.remove("__pycache__")
			for f in files:
				if f.endswith(".py"):
					src_path = os.path.join(root, f)
					rel_path = os.path.relpath(src_path, SRC_DIR)
					files_to_include.append((src_path, rel_path.replace("\\", "/")))

	# 3. locale/ directory (Only manifest.ini and LC_MESSAGES/nvda.mo)
	locale_dir = os.path.join(SRC_DIR, "locale")
	if os.path.exists(locale_dir):
		for lang in os.listdir(locale_dir):
			lang_dir = os.path.join(locale_dir, lang)
			if not os.path.isdir(lang_dir):
				continue
			
			# Localized manifest
			loc_manifest = os.path.join(lang_dir, "manifest.ini")
			if os.path.exists(loc_manifest):
				rel_path = os.path.relpath(loc_manifest, SRC_DIR)
				files_to_include.append((loc_manifest, rel_path.replace("\\", "/")))
			
			# Compiled gettext binary .mo
			mo_file = os.path.join(lang_dir, "LC_MESSAGES", "nvda.mo")
			if os.path.exists(mo_file):
				rel_path = os.path.relpath(mo_file, SRC_DIR)
				files_to_include.append((mo_file, rel_path.replace("\\", "/")))

	# 4. doc/ directory (Documentation files: .html, .css, .md)
	doc_dir = os.path.join(SRC_DIR, "doc")
	if os.path.exists(doc_dir):
		for root, dirs, files in os.walk(doc_dir):
			for f in files:
				ext = os.path.splitext(f)[1].lower()
				if ext in (".html", ".css", ".md", ".txt"):
					src_path = os.path.join(root, f)
					rel_path = os.path.relpath(src_path, SRC_DIR)
					files_to_include.append((src_path, rel_path.replace("\\", "/")))

	return files_to_include


def deploy_to_installed(whitelist):
	"""Deploys only the whitelisted addon files to the NVDA installation folder."""
	print("Deploying whitelisted files to NVDA installation folder...")
	if not os.path.exists(INSTALL_DIR):
		print(f"Error: Installed directory {INSTALL_DIR} does not exist!")
		return False

	# Clean target directory of stale/unwanted files
	shutil.rmtree(INSTALL_DIR, ignore_errors=True)
	os.makedirs(INSTALL_DIR, exist_ok=True)

	for src_path, rel_path in whitelist:
		dst_path = os.path.join(INSTALL_DIR, rel_path)
		os.makedirs(os.path.dirname(dst_path), exist_ok=True)
		shutil.copy2(src_path, dst_path)

	print(f"Successfully deployed {len(whitelist)} clean files to NVDA.")
	return True


def package_addon(whitelist):
	"""Creates a clean, minimal .nvda-addon archive with only the whitelisted files."""
	print(f"Packaging addon into {OUTPUT_ADDON}...")
	if os.path.exists(OUTPUT_ADDON):
		try:
			os.remove(OUTPUT_ADDON)
		except Exception as e:
			print(f"Error removing old addon file: {e}")
			return False

	with zipfile.ZipFile(OUTPUT_ADDON, "w", zipfile.ZIP_DEFLATED) as zf:
		for src_path, rel_path in whitelist:
			zf.write(src_path, rel_path)

	pkg_size_kb = os.path.getsize(OUTPUT_ADDON) / 1024
	print(f"Successfully packaged {len(whitelist)} clean files into {OUTPUT_ADDON} ({pkg_size_kb:.1f} KB).")
	return True


if __name__ == "__main__":
	print("=" * 60)
	print("      NVDA TRANSLATE: STRICT WHITELIST BUILD & DEPLOY       ")
	print("=" * 60)
	compile_locales()
	whitelist = get_whitelisted_addon_files()
	print(f"Found {len(whitelist)} whitelisted production files.")
	
	deploy_success = deploy_to_installed(whitelist)
	package_success = package_addon(whitelist)
	
	print("=" * 60)
	if deploy_success and package_success:
		print("Build, Deploy & Packaging completed successfully with ZERO clutter!")
	else:
		print("Process completed with errors.")
	print("=" * 60)
