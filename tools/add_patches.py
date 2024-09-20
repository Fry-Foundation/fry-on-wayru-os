import os
import subprocess
import sys
from dotenv import load_dotenv

load_dotenv()

PROFILE_NAME = os.getenv('PROFILE')
PROFILE_DIR = os.path.join("profiles", PROFILE_NAME)  # Ajuste para subir un nivel y entrar a profiles
PATCH_DIR = os.path.join(PROFILE_DIR, "patches")
OPENWRT_DIR = os.path.join("openwrt")  
#PROFILE_DIR = f"../profiles/{PROFILE_NAME}"
#PATCH_DIR = os.path.join(PROFILE_DIR, "patches")

def apply_patch(patch_file):
    try:
        with open(patch_file, 'r') as patch:
            print(f"Applying patch: {patch_file}")
            result = subprocess.run(
                ['patch', '-p1'],
                stdin=patch,
                cwd=OPENWRT_DIR,  
                check=True,
                text=True
            )
            if result.returncode == 0:
                print(f"Patch {patch_file} applied correctly")
    except subprocess.CalledProcessError as e:
        print(f"Error applying patch: {patch_file}")
        sys.exit(1)

def main():
    # Check if the profile folder exists
    if not os.path.exists(PROFILE_DIR):
        print(f"Profile directory not found: {PROFILE_DIR}")
        sys.exit(1)
    
    # Check if the patches subfolder exists
    if not os.path.exists(PATCH_DIR):
        print(f"Patch folder not found in profile: {PATCH_DIR}. this profile does not need them.")
        sys.exit(1)

    patch_files = [f for f in os.listdir(PATCH_DIR) if f.endswith('.patch')]

    if not patch_files:
        print(f"No patches were found in {PATCH_DIR}")
        sys.exit(0)

    # Apply patches
    for patch in patch_files:
        patch_file = os.path.join(PATCH_DIR, patch)
        apply_patch(patch_file)

if __name__ == "__main__":
    main()
