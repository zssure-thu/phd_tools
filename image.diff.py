#!/usr/bin/env python
import sys,os

outfile = sys.argv[-1]
infile1 = sys.argv[-2]
infile2 = sys.argv[-3]

os.popen("clitkImageArithm -t 7 -i "+infile1+" -j "+infile2+" -o "+outfile)
