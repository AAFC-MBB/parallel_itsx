#!/usr/bin/env python
from Bio import SeqIO
from threading import Thread
from glob import glob
from itsxcmd import ITSxCommandLine
from itsx import make_path, BinPacker, Bin
import os
import shutil
__author__ = 'mike knowles'


class ITSx(object):

    def __init__(self, i, o, cpu, **kwargs):
        from Queue import Queue
        self.threads = cpu
        self.path = o
        self.itsxargs = kwargs
        self.fasta = i
        self.itsxqueue = Queue()
        self.name = ""

    def parallel(self):
        while True:
            filename, output, cwd = self.itsxqueue.get()
            ITSxCommandLine(i=filename, o=self.name, cpu=self.threads, **self.itsxargs)(cwd=cwd)
            self.itsxqueue.task_done()

    def __call__(self, name=None):
        import math
        self.name = name if name else os.path.splitext(os.path.basename(self.fasta))[0]
        baselist = []
        for _ in range(self.threads):
            # Send the threads to the merge method. :args is empty as I'm using
            threads = Thread(target=self.parallel, args=())
            # Set the daemon to true - something to do with thread management
            threads.setDaemon(True)
            # Start the threading
            threads.start()
        with open(self.fasta) as fastafile:
            total = sum(map(len, SeqIO.parse(fastafile, "fasta")))
            fastafile.seek(0)
            cap = int(math.ceil(float(total) / self.threads))
            cap += int(cap / 2e4)
            record = SeqIO.parse(fastafile, "fasta")
            for i, batch in enumerate(BinPacker(record, cap)):
                base = os.path.join(self.path, str(i+1))
                output = os.path.join(base, self.name)
                make_path(base)
                filename = output + ".x"
                with open(filename, "w") as handle:
                    SeqIO.write(list(batch), handle, "fasta")
                self.itsxqueue.put((name + '.x', output, base))
                baselist.append(base)
        self.itsxqueue.join()
        finalfiles = glob(os.path.join(self.path, '1/*[!x]'))
        for output in finalfiles:
            # Low level file i/o operation to quickly append files without significant overhead
            if hasattr(os, 'O_BINARY'):
                o_binary = getattr(os, 'O_BINARY')
            else:
                o_binary = 0
            f = os.path.basename(output)
            output_file = os.open(os.path.join(self.path, f), os.O_WRONLY | o_binary | os.O_CREAT)
            for intermediate in baselist:
                input_filename = os.path.join(intermediate, f)
                input_file = os.open(input_filename, os.O_RDONLY | o_binary)
                while True:
                    input_block = os.read(input_file, 1024 * 1024)
                    if not input_block:
                        break
                    os.write(output_file, input_block)
                os.close(input_file)
            os.close(output_file)
        try:
            summarylines = self.summary(baselist)
            with open(os.path.join(self.path, self.name + '.summary.txt'), 'w+') as full:
                full.writelines(summarylines)
        except IOError:
            print "ITSx failed to run!"
        for intermediate in baselist:
            shutil.rmtree(intermediate)

    def summary(self, baselist):
        '''
        Compile summary report is generated by adding up all the values in temp .summary.txt files
        :param baselist: list of folders and temporary files
        :return: compiled summary report
        '''
        import re
        summarylines = list()
        regex = re.compile('\d+$')
        for intermediate in baselist:
            with open(os.path.join(intermediate, self.name + ".summary.txt")) as summary:
                if summarylines:
                    for idx, line in enumerate(summary):
                        match = regex.search(line)
                        if match:
                            summatch = regex.search(summarylines[idx])
                            start = match.start() if match.start() <= summatch.start() else summatch.start()
                            summarylines[idx] = '{0:s}{1:d}\n'.format(summarylines[idx][:start],
                                                                      int(match.group(0)) + int(summatch.group(0)))
                else:
                    summarylines = summary.readlines()
        return summarylines


if __name__ == '__main__':
    pass
