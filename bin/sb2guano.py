#!/usr/bin/env python2
"""
Convert files with Sonobat-format metadata to use GUANO metadata.

usage: sb2guano.py WAVFILE...
"""

import sys
import os
import os.path
import mmap
import re
import wave
from contextlib import closing
from datetime import datetime
from pprint import pprint

from guano import GuanoFile


# regex for parsing Sonobat metadata
SB_MD_REGEX = re.compile(r'MMMMMMMMM(?P<sb_md>[\w\W]+)MMMMMMMMM')
SB_FREQ_REGEX = re.compile(r'\(#([\d]+)#\)')
SB_TE_REGEX = re.compile(r'<&([\d]*)&>')
SB_DFREQ_REGEX = re.compile(r'\[!([\w]+)!\]')

# old SonoBat format e.g. TransectTestRun1-24Mar11-16,27,56-Myoluc.wav
SONOBAT_FILENAME1_REGEX = re.compile(r'(?P<date>[ 0123][0-9][A-Z][a-z][a-z][0-9][0-9]-[012][0-9],[0-6][0-9],[0-6][0-9])(-(?P<species>[A-Za-z]+))?')
SONOBAT_FILENAME1_TIMESTAMP_FMT = '%d%b%y-%H,%M,%S'

# new SonoBat format 4-digit year e.g. TransectTestRun1-20110324_162756-Myoluc.wav
SONOBAT_FILENAME2_REGEX = re.compile(r'(?P<date>\d{8}_\d{6})(-(?P<species>[A-Za-z]+))?')
SONOBAT_FILENAME2_TIMESTAMP_FMT = '%Y%m%d_%H%M%S'

# new new SonoBat format 2-digit year e.g. TransectTestRun1-20110324_162756-Myoluc.wav
SONOBAT_FILENAME3_REGEX = re.compile(r'(?P<date>\d{6}_\d{6})(-(?P<species>[A-Za-z]+))?')
SONOBAT_FILENAME3_TIMESTAMP_FMT = '%y%m%d_%H%M%S'

# AR125 raw
AR125_FILENAME_REGEX = re.compile(r'_(?P<date>D\d{8}T\d{6})m\d{3}(-(?P<species>[A-Za-z]+))?')
AR125_FILENAME_TIMESTAMP_FMT = 'D%Y%m%dT%H%M%S'

SB_FILENAME_FORMATS = [
    (SONOBAT_FILENAME1_REGEX, SONOBAT_FILENAME1_TIMESTAMP_FMT),
    (SONOBAT_FILENAME2_REGEX, SONOBAT_FILENAME2_TIMESTAMP_FMT),
    (SONOBAT_FILENAME3_REGEX, SONOBAT_FILENAME3_TIMESTAMP_FMT),
    (AR125_FILENAME_REGEX,    AR125_FILENAME_TIMESTAMP_FMT)
]


def extract_sonobat_metadata(fname):
    """Extract Sonobat-format metadata as a dict"""
    sb_md = {}

    # parse the Sonobat metadata itself
    with open(fname, 'rb') as infile:
        with closing(mmap.mmap(infile.fileno(), 0, access=mmap.ACCESS_READ)) as mmfile:
            md_match = re.search(SB_MD_REGEX, mmfile)
            if not md_match:
                print >> sys.stderr, 'No Sonobat metadata found in file: ' + fname
                return None
            md = md_match.groups()[0]
            sb_md['samplerate'] = int(re.search(SB_FREQ_REGEX, md).groups()[0])
            sb_md['te'] = int(re.search(SB_TE_REGEX, md).groups()[0])
            sb_md['dfreq'] = re.search(SB_DFREQ_REGEX, md).groups()[0]
            sb_md['note'] = md.split('!]', 1)[1]

    with closing(wave.open(fname)) as wavfile:
        duration_s = wavfile.getnframes() / float(wavfile.getframerate())
        sb_md['length'] = duration_s / sb_md['te']

    # try to extract info from the filename
    for regex, timestamp_fmt in SB_FILENAME_FORMATS:
        match = regex.search(fname)
        if match:
            sb_md['timestamp'] = datetime.strptime(match.group('date'), timestamp_fmt)
            sb_md['species'] = match.group('species')

    return sb_md


def sonobat2guano(fname):
    """Convert a file with Sonobat metadata to GUANO metadata"""
    print '\n', fname
    sb_md = extract_sonobat_metadata(fname)
    if not sb_md:
        print >> sys.stderr, 'Skipping non-Sonobat file: ' + fname
        return False
    pprint(sb_md)

    gfile = GuanoFile(fname)
    gfile['GUANO|Version'] = 1.0
    if 'timestamp' in sb_md:
        gfile['Timestamp'] = sb_md['timestamp']
    if sb_md.get('te', 1) != 1:
        gfile['TE'] = sb_md['te']
    gfile['Length'] = sb_md['length']
    gfile['Note'] = sb_md['note'].strip().replace('\r\n', '\\n').replace('\n', '\\n')
    if sb_md.get('species', None):
        gfile['Species Auto ID'] = sb_md['species']
    print gfile._as_string()

    gfile.write()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print >> sys.stderr, 'usage: %s FILE...' % os.path.basename(sys.argv[0])
        sys.exit(2)

    if os.name == 'nt' and '*' in sys.argv[1]:
        from glob import glob
        fnames = glob(sys.argv[1])
    else:
        fnames = sys.argv[1:]

    for fname in fnames:
        sonobat2guano(fname)
