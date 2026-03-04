/* clawd.rexx - OpenClaw ↔ Amiga listener (ARexx) */
/* Runs on AmigaOS 2.x/3.x with RexxMast started (usually automatic). */

OPTIONS RESULTS
OPTIONS FAILAT 9999

/* ---------- config ---------- */
base = ARG(1)
IF base = '' THEN base = 'Shared:openclaw'

inDir  = base || '/in'
outDir = base || '/out'
logDir = base || '/log'

pollTicks = 10      /* 1 tick ~ 1/50s on PAL; we also use Wait. */
sleepSec  = 1

CALL EnsureDir base
CALL EnsureDir inDir
CALL EnsureDir outDir
CALL EnsureDir logDir

CALL Log 'clawd started. base='||base

DO FOREVER
  /* Find next job file (first one in List output) */
  job = NextJob(inDir)
  IF job = '' THEN DO
     CALL Wait sleepSec
     ITERATE
  END

  CALL Log 'job found: '||job

  jobPath = inDir || '/' || job
  /* Parse job */
  PARSE VALUE ReadFirstLine(jobPath) WITH firstline
  IF firstline ~= 'CLAWJOB 1' THEN DO
     CALL Log 'invalid magic in '||job
     CALL SafeDelete jobPath
     ITERATE
  END

  id = GetKV(jobPath, 'id')
  action = Lower(GetKV(jobPath, 'action'))

  IF id = '' THEN id = Strip(DelStr(job, Pos('.', job))) /* from filename */

  IF action = 'stop' THEN DO
     CALL Log 'stop requested. exiting.'
     CALL SafeDelete jobPath
     EXIT 0
  END

  IF action ~= 'run' THEN DO
     CALL WriteResult outDir, id, 0, 20, 'Unknown action: '||action
     CALL SafeDelete jobPath
     ITERATE
  END

  cmd = GetKV(jobPath, 'cmd')
  cwd = GetKV(jobPath, 'cwd')
  waitms = GetKV(jobPath, 'wait_ms')

  IF cmd = '' THEN DO
     CALL WriteResult outDir, id, 0, 10, 'Missing cmd='
     CALL SafeDelete jobPath
     ITERATE
  END

  /* Execute command and capture output */
  outFile = outDir || '/' || id || '.out'
  resFile = outDir || '/' || id || '.res'
  tmpScript = 'T:claw_' || id || '.script'
  tmpOut = 'T:claw_' || id || '.tmpout'

  CALL SafeDelete outFile
  CALL SafeDelete resFile
  CALL SafeDelete tmpScript
  CALL SafeDelete tmpOut

  /* Build script if cwd set */
  IF cwd ~= '' THEN DO
     CALL WriteTextFile tmpScript, 'CD ' || cwd || "\n" || cmd || "\n"
     fullCmd = 'Execute ' || tmpScript || ' >' || tmpOut
  END
  ELSE DO
     fullCmd = cmd || ' >' || tmpOut
  END

  CALL Log 'exec: '||fullCmd

  ADDRESS COMMAND fullCmd
  rc = RC

  /* Copy tmpOut -> outFile (Shared volume) */
  IF Exists(tmpOut) THEN DO
     ADDRESS COMMAND 'Copy ' || tmpOut || ' ' || outFile || ' QUIET'
  END
  ELSE DO
     CALL WriteTextFile outFile, ''
  END

  /* Optional wait */
  IF waitms ~= '' THEN DO
     w = waitms + 0
     IF w > 0 THEN DO
        secs = w % 1000
        IF secs < 1 THEN secs = 1
        CALL Wait secs
     END
  END

  ok = 1
  IF rc ~= 0 THEN ok = 0

  /* For very short outputs, also inline in .res as single line (trimmed) */
  outInline = ReadFirstLine(outFile)
  outInline = Strip(outInline)
  IF Length(outInline) > 120 THEN outInline = SubStr(outInline,1,120) || '...'

  CALL WriteResultWithFile outDir, id, ok, rc, outInline, outFile

  /* Delete job file (ack) */
  CALL SafeDelete jobPath

  /* Cleanup temps */
  CALL SafeDelete tmpScript
  CALL SafeDelete tmpOut
END

EXIT 0

/* ---------- helpers ---------- */

EnsureDir: PROCEDURE
  p = ARG(1)
  IF ~Exists(p) THEN DO
     ADDRESS COMMAND 'MakeDir ' || p
  END
RETURN

SafeDelete: PROCEDURE
  p = ARG(1)
  IF Exists(p) THEN ADDRESS COMMAND 'Delete ' || p || ' QUIET'
RETURN

Log: PROCEDURE EXPOSE logDir
  msg = ARG(1)
  ts = DATE('S') || ' ' || TIME()
  lf = logDir || '/clawd.log'
  /* append */
  ADDRESS COMMAND 'Echo "'||EscapeQuotes(ts||' '||msg)||'" >>' || lf
RETURN

EscapeQuotes: PROCEDURE
  s = ARG(1)
  /* replace " with \" (DOS Echo accepts ") */
  s = Changestr('"', s, '\\"')
RETURN s

Lower: PROCEDURE
  RETURN LOWER(ARG(1))

ReadFirstLine: PROCEDURE
  f = ARG(1)
  IF ~Exists(f) THEN RETURN ''
  IF ~OPEN('R', f, 'R') THEN RETURN ''
  line = READLN('R')
  CALL CLOSE('R')
RETURN line

WriteTextFile: PROCEDURE
  f = ARG(1)
  txt = ARG(2)
  /* Normalize line endings */
  txt = ChangeStr("\r", txt, "")
  IF OPEN('W', f, 'W') THEN DO
     /* Split by LF and write line by line */
     DO WHILE txt ~= ''
        p = POS("\n", txt)
        IF p = 0 THEN DO
           line = txt
           txt = ''
        END
        ELSE DO
           line = SUBSTR(txt, 1, p-1)
           txt  = SUBSTR(txt, p+1)
        END
        CALL WRITELN 'W', line
     END
     CALL CLOSE('W')
  END
RETURN

GetKV: PROCEDURE
  f = ARG(1)
  key = ARG(2)
  k = key || '='
  val = ''
  IF ~Exists(f) THEN RETURN ''
  IF ~OPEN('R', f, 'R') THEN RETURN ''
  DO WHILE ~EOF('R')
     line = READLN('R')
     line = STRIP(line)
     IF line = '' THEN ITERATE
     IF LEFT(line,1) = '#' THEN ITERATE
     IF LEFT(line, LENGTH(k)) = k THEN DO
        val = SUBSTR(line, LENGTH(k)+1)
        LEAVE
     END
  END
  CALL CLOSE('R')
RETURN STRIP(val)

NextJob: PROCEDURE
  dir = ARG(1)
  tmp = 'T:claw_jobs.txt'
  ADDRESS COMMAND 'List '||dir||' PAT #?.job LFORMAT "%N" >'||tmp
  job = ''
  IF Exists(tmp) THEN DO
     IF OPEN('R', tmp, 'R') THEN DO
        IF ~EOF('R') THEN job = STRIP(READLN('R'))
        CALL CLOSE('R')
     END
  END
  IF job = '' THEN DO
     /* try without PAT (older systems) */
     ADDRESS COMMAND 'List '||dir||' LFORMAT "%N" >'||tmp
     IF Exists(tmp) THEN DO
        IF OPEN('R', tmp, 'R') THEN DO
           DO WHILE ~EOF('R')
              l = STRIP(READLN('R'))
              IF RIGHT(l,4) = '.job' THEN DO
                 job = l
                 LEAVE
              END
           END
           CALL CLOSE('R')
        END
     END
  END
  ADDRESS COMMAND 'Delete '||tmp||' QUIET'
RETURN job

WriteResult: PROCEDURE
  outDir = ARG(1)
  id = ARG(2)
  ok = ARG(3)
  rc = ARG(4)
  output = ARG(5)

  resFile = outDir || '/' || id || '.res'
  txt = 'CLAWRES 1' || "\n" || ,
        'id='||id||"\n"||,
        'ok='||ok||"\n"||,
        'rc='||rc||"\n"||,
        'output='||SanitizeOneLine(output)||"\n"
  CALL WriteTextFile resFile, txt
RETURN

WriteResultWithFile: PROCEDURE
  outDir = ARG(1)
  id = ARG(2)
  ok = ARG(3)
  rc = ARG(4)
  output = ARG(5)
  outFile = ARG(6)

  resFile = outDir || '/' || id || '.res'
  txt = 'CLAWRES 1' || "\n" || ,
        'id='||id||"\n"||,
        'ok='||ok||"\n"||,
        'rc='||rc||"\n"||,
        'output='||SanitizeOneLine(output)||"\n"||,
        'output_file='||outFile||"\n"
  CALL WriteTextFile resFile, txt
RETURN

SanitizeOneLine: PROCEDURE
  s = ARG(1)
  s = Changestr("\n", s, " ")
  s = Changestr("\r", s, " ")
RETURN STRIP(s)
