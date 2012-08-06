import os
from django.conf import settings
from madrona.common.utils import get_logger
from shutil import copyfile
log = get_logger()

class MarxanError(Exception):
    pass

class MarxanAnalysis(object):

    def __init__(self, pucosts, cfs, outdir, name="nplcc"):
        self.outdir = os.path.realpath(outdir)
        self.marxan_bin = os.path.realpath(settings.MARXAN_BIN)
        if not os.path.exists(self.marxan_bin):
            raise MarxanError("Marxan linux binary not found; tried %s" % self.marxan_bin)
        if not os.access(self.marxan_bin, os.X_OK):
            raise MarxanError("Marxan binary exists but is not executable; tried %s" % self.marxan_bin)

        self.NUMREPS = settings.MARXAN_NUMREPS
        self.NUMITNS = settings.MARXAN_NUMITNS
        self.templatedir = settings.MARXAN_TEMPLATEDIR

        self.pus = pucosts 
        self.cfs = cfs 
        self.name = name

    def setup(self):
        if os.path.exists(self.outdir):
            import shutil 
            shutil.rmtree(self.outdir) 
        os.makedirs(os.path.join(self.outdir, "data"))
        os.makedirs(os.path.join(self.outdir, "output"))

        link = os.path.realpath(os.path.join(self.outdir, "marxan"))
        if not os.path.exists(link):
            os.symlink(self.marxan_bin, link)

    def write_pu(self):
        fh = open("%s/data/pu.dat" % self.outdir, 'w')
        fh.write(",".join(["id", "cost", "status"]))
        for w in self.pus:
            fh.write("\n")
            fh.write(",".join(str(x) for x in [w[0], w[1], 0]))
        fh.close()

    def write_puvcf(self):
        out = "%s/data/puvcf.dat" % self.outdir
        template = os.path.join(self.templatedir, 'puvcf.dat')
        if os.path.exists(template):
            outfh = open(out, 'w')
            inlines = open(template, 'r').readlines()
            outfh.write(inlines[0])
            puids = [x[0] for x in self.pus]
            for line in inlines[1:]:
                line_items = line.split(',')
                puid = int(line_items[1])
                amount = line_items[2].strip()
                if amount == '' or not amount:
                    amount = 0  # TODO appropos to turn nulls to 0?
                if puid in puids:
                    # Only write the line IF the planning unit is in the geography!
                    # Important - must have exactly 100% density of matrix
                    # i.e. number of output rows == planning_units * species
                    outfh.write(','.join([str(x) for x in [line_items[0], puid, amount]]))
                    outfh.write('\n')
            outfh.close() 
            #copyfile(template, out)
        
    def write_spec(self):
        fh = open("%s/data/spec.dat" % self.outdir, 'w')
        fh.write(",".join(['id', 'type', 'target', 'spf', 'name']))
        for s in self.cfs:
            fh.write("\n")
            fh.write(",".join(str(x) for x in [s[0], 0, s[1], s[2], s[3].replace(",", '')]))
            
        fh.close()

    def write_input(self):
        out = "%s/input.dat" % self.outdir
        template = os.path.join(settings.MARXAN_TEMPLATEDIR, 'input.dat')
        if os.path.exists(template):
            copyfile(template, out)
        else:
            input_dat = """Input file for Annealing program.

This file generated by Marxan.py

General Parameters
VERSION 0.1
BLM  0.00000000000000E+0000
PROP  0.00000000000000E+0000
RANDSEED -1
BESTSCORE -1
NUMREPS %d

Annealing Parameters
NUMITNS %d
STARTTEMP -1
NUMTEMP 10000

Cost Threshold
COSTTHRESH  0.00000000000000E+0000
THRESHPEN1  0.00000000000000E+0000
THRESHPEN2  0.00000000000000E+0000

Input Files
INPUTDIR data
SPECNAME spec.dat
PUNAME pu.dat
PUVSPRNAME puvcf.dat

Save Files
SCENNAME %s
SAVERUN 3
SAVEBEST 3
SAVESUMMARY 3
SAVESCEN 3
SAVETARGMET 3
SAVESUMSOLN 3
SAVEPENALTY 3
SAVELOG 2
OUTPUTDIR output

Program control.
RUNMODE 1
MISSLEVEL 0.98
CLUMPTYPE 0
VERBOSITY 3
""" % (self.NUMREPS, self.NUMITNS, self.name)

            fh = open(out,'w')
            fh.write(input_dat)
            fh.close()


    def run(self):
        os.chdir(self.outdir)
        import subprocess
        proc = subprocess.Popen(
                ['./marxan'], 
                shell=True, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
        ) 
        print str(proc.communicate()[0])[:800] + "....."

    @property 
    def best(self):
        os.chdir(self.outdir)
        fname = os.path.realpath("%s/output/%s_best.csv" % (self.outdir, self.name))
        try:
            fh = open(fname ,'r')
        except IOError:
            log.error("Marxan output file %s was not found" % fname) 
            raise MarxanError("Error: analyis output files could not be found") 

        unit_status = [x.strip().split(',') for x in fh.readlines()]
        pks = []
        for u in unit_status[1:]:
            if int(u[1]) == 1:
                pks.append(int(u[0]))
            elif int(u[1]) > 1:
                log.warn("Check the _best.csv file .. got one with status > 1!") 
        fh.close()
        return pks
