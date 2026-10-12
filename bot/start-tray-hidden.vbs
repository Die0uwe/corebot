' Start de SB AI-bot tray-starter zonder venster (voor Starten met Windows).
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
py = dir & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(py) Then
  MsgBox "Eerst start-tray.bat uitvoeren (maakt de Python-omgeving).", 48, "SB AI-bot"
  WScript.Quit 1
End If
sh.Run """" & py & """ """ & dir & "\tray.py"" --minimized", 0, False
