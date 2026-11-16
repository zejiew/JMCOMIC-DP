' 双击运行（无黑色控制台窗口）
Option Explicit
Dim fso, shell, base, py, target
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)
target = base & "\run.py"

If fso.FileExists(base & "\.venv\Scripts\pythonw.exe") Then
    py = base & "\.venv\Scripts\pythonw.exe"
Else
    py = "pythonw.exe"
End If

shell.CurrentDirectory = base
shell.Run """" & py & """ """ & target & """", 0, False
