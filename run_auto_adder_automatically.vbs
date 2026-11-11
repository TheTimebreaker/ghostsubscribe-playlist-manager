' Create a shell object
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")
objShell.CurrentDirectory = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Run the auto adder from the project virtual environment
Dim strArgs
strArgs = "cmd /c .\.venv\Scripts\python.exe .\src\launcher.py -aaa"
objShell.Run strArgs, 0, False

' Cleanup
Set objShell = Nothing
Set objFSO = Nothing