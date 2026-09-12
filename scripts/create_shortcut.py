import os
import subprocess

desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
shortcut_path = os.path.join(desktop, "CatCam AI Monitor.lnk")
target_exe = r"C:\Projetos\catcam\.venv\Scripts\pythonw.exe"
target_script = r"C:\Projetos\catcam\catcam_tray.py"
working_dir = r"C:\Projetos\catcam"
icon_path = r"C:\Projetos\catcam\assets\catcam.ico"

vbs_content = f'''Set oWS = WScript.CreateObject("WScript.Shell")
Set oLink = oWS.CreateShortcut("{shortcut_path}")
oLink.TargetPath = "{target_exe}"
oLink.Arguments = "{target_script}"
oLink.WorkingDirectory = "{working_dir}"
oLink.IconLocation = "{icon_path},0"
oLink.Description = "CatCam AI - Visão Computacional e Monitoramento de Pets"
oLink.Save
'''

vbs_file = "temp_shortcut.vbs"
with open(vbs_file, "w", encoding="utf-8") as f:
    f.write(vbs_content)

subprocess.run(["cscript", "//nologo", vbs_file], check=True)
if os.path.exists(vbs_file):
    os.remove(vbs_file)

print(f"Atalho criado com sucesso no Desktop: {os.path.exists(shortcut_path)}")
