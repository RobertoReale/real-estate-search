' ============================================================================
'  Launch the Real Estate Search backend with NO console window.
'
'  Used by the "autostart" options in README.md:
'    A) put a shortcut to this file in the Startup folder (shell:startup), or
'    B) point a Task Scheduler task at it ("At log on").
'  Both run it in your user session, hidden. For a boot-time service that
'  survives logout and restarts on crash, use install-service.bat (NSSM) instead.
'
'  Prerequisite: build the dashboard once so the backend serves it on port 8000
'  (run serve.bat once, or: cd frontend && npm run build).
' ============================================================================
Dim sh, root, pyw
Set sh = CreateObject("WScript.Shell")

' Folder this script lives in (the project root), with trailing backslash.
root = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

' pythonw.exe runs Python without a console window (unlike python.exe).
pyw = root & "backend\.venv\Scripts\pythonw.exe"

If Not CreateObject("Scripting.FileSystemObject").FileExists(pyw) Then
    MsgBox "Backend virtual environment not found:" & vbCrLf & pyw & vbCrLf & _
           "Run start.bat once first so it creates backend\.venv.", _
           vbExclamation, "Real Estate Search"
    WScript.Quit 1
End If

sh.CurrentDirectory = root & "backend"
' 0 = hidden window, False = don't wait for it to exit
sh.Run """" & pyw & """ run.py", 0, False
