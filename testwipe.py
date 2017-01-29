#! python
# -*- coding: utf-8 -*-

"""
***
*** testwipe.py
*** version 0.85 (in development, milestone 2 build to upload as repo)
***
*** Written for Python 2.6+
***
*** Owner: Andrew Ziem
*** Author: Peter Marshall
***
***
*** Test suite for filewipe.py
***
*** Useful tools for testing:
***
*** WinHex (run as administrator)
*** ^^ For viewing the volume as raw clusters (sector editor type view)
*** WinHex can also write any kind of fill pattern to a disk.
"""


from __future__ import with_statement

import unittest
import sys
import os
import logging
from optparse import OptionParser
from glob import glob
from math import floor

from filewipe import *


# Constants.
test_folder_default = "E:\\"
file_name = "junk.txt"
file_name_tiny = "tiny.txt"
file_name_long = "this goes far beyond eight point three"
file_name_cmpr = "compressed.dat"
file_name_sparse = "sparse.dat"
file_name_encr = "encrypted.dat"
file_name_unicode = u"سلام"


# Create a file filled with random data.
def write_random_test_file(file_name, file_size):
    with open(file_name, 'wb') as f:
        f.write(os.urandom(file_size))


# Create a file filled with data that will compress easily.
def write_compressable_test_file(file_name, file_size):
    with open(file_name, 'wb') as f:
        f.write(''.rjust(file_size, '|'))


# Fill the volume to a specified percentage.
# Can be useful to stress test by making the volume approach a full state.
def fill_volume_to_pct(volume, fill_pct):
    # Check parameters.
    assert (fill_pct > 0 and fill_pct < 100)

    # Determine total number of bytes on volume.
    _, _, _, a, b, total_clusters = get_volume_information(volume)
    bytes_per_cluster = a * b
    total_bytes = bytes_per_cluster * total_clusters
    assert total_bytes > 0

    if volume and volume[-1] != os.sep:
        volume += os.sep
    volume_handle = obtain_readwrite(volume)

    file_index = 1
    while True:
        volume_bitmap, _ = get_volume_bitmap(volume_handle, total_clusters)
        free, allocated = check_extents(
            [(0, total_clusters - 1)], volume_bitmap)
        if 100 * allocated / total_clusters >= fill_pct:
            break
        file_name = volume + "bbfill%03d.dat" % file_index
        write_random_test_file(file_name, int(total_bytes * 0.01))
        print("Wrote %s.  Free %d; allocated %d" %
              (file_name, free, allocated))
        file_index += 1


# Figure out if a certain text is anywhere on the volume.
# Return True if found, False otherwise.
def search_volume_for_string(volume, search_text):
    found_string = False

    # Determine total number of bytes on volume.
    _, _, _, a, b, c = get_volume_information(volume)
    total_bytes = a * b * c
    assert total_bytes > 0

    # We need the FILE_SHARE flags so that this open call can succeed
    # despite something on the volume being in use by another process.
    volume = '\\\\.\\' + volume
    if volume[-1] == os.sep:
        volume = volume.rstrip(os.sep)
    volume_handle = CreateFile(volume, GENERIC_READ,
                               FILE_SHARE_READ | FILE_SHARE_WRITE,
                               None, OPEN_EXISTING, 0, None)
    logging.debug("Opened %s for text search", volume)

    # Seek to the beginning of the volume where we will read.
    SetFilePointer(volume_handle, 0, FILE_BEGIN)

    # Loop and perform reads of write_buf_size bytes or less.
    # Continue until we reach the end of the volume.
    bytes_remaining = total_bytes
    while bytes_remaining > 0:
        hr, read_buf = ReadFile(volume_handle, write_buf_size)
        if hr != 0:
            logging.error("!! A read error %d occurred !!", hr)
            return False
        find_result = read_buf.find(search_text)
        if find_result >= 0:
            found_cluster = int(floor((total_bytes - bytes_remaining
                                            + find_result) / (a * b)))
            logging.error("Search text found near cluster %d.", found_cluster)
            volume_bitmap, _ = get_volume_bitmap(volume_handle, c)
            if not check_mapped_bit(volume_bitmap, found_cluster):
                logging.error("That sector is free.")
            else:
                logging.error("That sector is allocated.")
            found_string = True
        bytes_remaining -= len(read_buf)

    # We've read through entire volume, search text wasn't found.
    return found_string


class bbTest(unittest.TestCase):

    def clean_test_files(self):
        for delfile in [file_name, file_name_tiny, file_name_long,
                        file_name_cmpr, file_name_sparse, file_name_encr]:
            try:
                os.remove(test_folder + os.sep + delfile)
            except:
                pass
        try:
            os.remove(unicode(test_folder + os.sep) + file_name_unicode)
        except:
            pass
        [os.remove(x) for x in glob(test_folder + "bbspike*")]

    def setUp(self):
        self.clean_test_files()
        
    def tearDown(self):
        self.clean_test_files()


    def test_file_operations(self):
        print("Test file attributes and truncate...")
        file_path = test_folder + os.sep + file_name
        os.system('echo | set /p="abcde11111" >%s' % file_path)
        file_handle = open_file(file_path, GENERIC_READ | GENERIC_WRITE)
        file_size, is_special = get_file_basic_info(file_path, file_handle)
        self.assertEqual(file_size, 10,
                         "Basic string file size as expected")
        truncate_file(file_handle)
        file_size, is_special = get_file_basic_info(file_path, file_handle)
        self.assertEqual(file_size, 0,
                         "Truncated file size is 0")
        CloseHandle(file_handle)

    def test_file_wipe_no_extents(self):
        print("Test file wipe where no extents...")
        file_path = test_folder + os.sep + file_name_tiny
        write_random_test_file(file_path, 32)
        with open(file_path, 'rb') as f:
            search_token = f.read()
        file_wipe(file_path)
        if not noverify:
            found_string = search_volume_for_string(
                       volume_from_file(file_path), search_token)
            self.assertFalse(found_string,
                "Search token should not appear during search of entire volume")
        
    def test_long_file_name(self):
        print("Test long file name...")
        file_path = test_folder + os.sep + file_name_long
        write_random_test_file(file_path, 7 * 1024)
        file_wipe(file_path)

    def test_unicode_file_name(self):
        print("Test unicode file name...")
        file_path = unicode(test_folder + os.sep) + file_name_unicode
        write_random_test_file(file_path, 7 * 1024)
        file_wipe(file_path)

    def test_larger_file_wipe(self):
        print("Test wipe 7MB file...")
        file_path = test_folder + os.sep + file_name_long
        write_random_test_file(file_path, 7 * 1024**2)
        with open(file_path, 'rb') as f:
            # Seek to somewhere near the middle.
            f.seek(3123456)
            search_token = f.read(32)
        assert len(search_token) == 32
        file_wipe(file_path)
        if not noverify:
            found_string = search_volume_for_string(
                volume_from_file(file_path), search_token)
            self.assertFalse(found_string,
                             "Search token should not appear during search of entire volume")

    def test_well_compressed_file_wipe(self):
        # only applies on NTFS
        file_path = test_folder + os.sep + file_name_cmpr
        volume = volume_from_file(file_path)
        info = get_volume_information(volume)
        if info[2].upper() != "NTFS":
            print("Well compressed file wipe test case not run - " +
                  "file system doesn't support it")
            return

        print("Test wipe well compressed file...")
        write_compressable_test_file(file_path, 5 * 1024**2)
        with open(file_path, 'rb') as f:
            # Seek to somewhere near the middle.
            f.seek(2813456)
            search_token = f.read(32)
        assert len(search_token) == 32
        file_handle = open_file(file_path, GENERIC_READ | GENERIC_WRITE)
        file_make_compressed(file_handle)
        CloseHandle(file_handle)
        file_wipe(file_path)
        if not noverify:
            found_string = search_volume_for_string(
                volume_from_file(file_path), search_token)
            self.assertFalse(found_string,
                             "Search token should not appear during search of entire volume")

    def test_hardly_compressed_file_wipe(self):
        # only applies on NTFS
        file_path = test_folder + os.sep + file_name_cmpr
        volume = volume_from_file(file_path)
        info = get_volume_information(volume)
        if info[2].upper() != "NTFS":
            print("Hardly compressed file wipe test case not run - " +
                  "file system doesn't support it")
            return

        print("Test wipe hardly compressed file...")
        write_random_test_file(file_path, 5 * 1024**2)
        with open(file_path, 'rb') as f:
            # Seek to somewhere near the middle.
            f.seek(2813456)
            search_token = f.read(32)
        assert len(search_token) == 32
        file_handle = open_file(file_path, GENERIC_READ | GENERIC_WRITE)
        file_make_compressed(file_handle)
        CloseHandle(file_handle)
        file_wipe(file_path)
        if not noverify:
            found_string = search_volume_for_string(
                volume_from_file(file_path), search_token)
            self.assertFalse(found_string,
                             "Search token should not appear during search of entire volume")

    def test_sparse_file_wipe(self):
        # only applies on NTFS
        file_path = test_folder + os.sep + file_name_sparse
        volume = volume_from_file(file_path)
        info = get_volume_information(volume)
        if info[2].upper() != "NTFS":
            print("Sparse file wipe test case not run - " +
                  "file system doesn't support it")
            return

        print("Test wipe sparse file...")
        write_random_test_file(file_path, 5 * 1024**2)
        with open(file_path, 'rb') as f:
            # Seek to somewhere near the middle.
            f.seek(2813456)
            search_token = f.read(32)
        assert len(search_token) == 32
        file_handle = open_file(file_path, GENERIC_READ | GENERIC_WRITE)
        file_make_sparse(file_handle)
        file_add_sparse_region(
            file_handle, 50000, 128000)      # within existing
        file_add_sparse_region(file_handle, 5000000, 7000000)   # beyond end
        CloseHandle(file_handle)
        file_wipe(file_path)
        if not noverify:
            found_string = search_volume_for_string(
                volume_from_file(file_path), search_token)
            self.assertFalse(found_string,
                             "Search token should not appear during search of entire volume")

    def test_encrypted_file_wipe(self):
        # only applies on NTFS
        file_path = test_folder + os.sep + file_name_encr
        volume = volume_from_file(file_path)
        info = get_volume_information(volume)
        if info[2].upper() != "NTFS":
            print("Encrypted file wipe test case not run - " +
                  "file system doesn't support it")
            return
        _, is_home = determine_win_version()
        if is_home:
            print("Encrypted file wipe test case not run - " +
                  "Windows Home does not allow encryption on individual files")
            return

        print("Test wipe encrypted file...")
        write_random_test_file(file_path, 5 * 1024**2)
        with open(file_path, 'rb') as f:
            # Seek to somewhere near the middle.
            f.seek(2813456)
            search_token = f.read(32)
        assert len(search_token) == 32
        EncryptFile(file_path)
        file_wipe(file_path)
        if not noverify:
            found_string = search_volume_for_string(
                volume_from_file(file_path), search_token)
            self.assertFalse(found_string,
                             "Search token should not appear during search of entire volume")

    def test_volume_operations(self):
        print("Test volume info gathering...")
        file_path = test_folder + os.sep + file_name
        volume = volume_from_file(file_path)
        info = get_volume_information(volume)
        self.assertEqual(len(info), 6,
                         "Volume info structure returns expected element count")
        self.assertEqual(info[4] % 512, 0,
                         "Cluster size is a multiple of 512")
        self.assertTrue(info[4] > 0,
                         "Cluster size is a positive number")

    def test_logical_ranges_to_extents(self):
        print("Test logical ranges to extents...")
        self.assertEqual([], [x for x in logical_ranges_to_extents([])],
                         "Logical ranges to extents empty list")
        self.assertEqual([(1040, 1053)],
                         [x for x in logical_ranges_to_extents([(14, 1040)])],
                         "Logical ranges to extents one tuple")
        self.assertEqual([(1040, 1053), (9999, 10037)],
                         [x for x in logical_ranges_to_extents(
                             [(14, 1040), (16, -1), (55, 9999), (66, -1)])],
                         "Logical ranges to extents simulate compressed extents")

    def test_get_extents(self):
        print("Test get extents...")
        file_path = test_folder + os.sep + file_name_tiny
        os.system('echo | set /p="abcde12345" >%s' % file_path)
        file_handle = open_file(file_path, GENERIC_READ)
        extents = get_extents(file_handle, False)
        volume = volume_from_file(file_path)
        info = get_volume_information(volume)
        # only applies on NTFS
        if info[2].upper() == "NTFS":
            self.assertEqual(extents, [],
                             "Get extents; tiny file that fits entirely on MFT")
        CloseHandle(file_handle)
        file_path = test_folder + os.sep + file_name
        write_random_test_file(file_path, 7 * 1024)
        file_handle = open_file(file_path, GENERIC_READ)
        extents = get_extents(file_handle, False)
        logging.debug(extents)
        self.assertNotEqual(len(extents), 0,
                            "Get extents; simple file returns at least one extent")
        for rec in extents:
            self.assertEqual(len(rec), 2,
                             "Get extents; each extent is a 2-tuple")
            lcn_start, lcn_end = rec
            self.assertTrue(lcn_start <= lcn_end,
                            "Get extents; each extent start <= end")


if __name__ == '__main__':
    # Look at command line arguments.
    parser = OptionParser(usage="testwipe.py test|wipe|search|fill [options]",
                          epilog="""
For test, no flags are required; can use -n for speed.    
For wipe, the -f flag is required.    
For search, both the -f and -s flags are required.    
For fill, both the -f and -p flags are required.""")
    parser.add_option("-n", "--noverify", action="store_true", dest="noverify",
                      help="run the test suite without verifying wipe result")
    parser.add_option("-d", "--debug", action="store_true", dest="debug",
                      help="show debug level (verbose) output")
    parser.add_option("-f", "--file", dest="file",
                      help="file or volume", metavar="FILE")
    parser.add_option("-s", "--search", dest="search", metavar="STRING",
                      help="string to search for")
    parser.add_option("-p", "--percent", type="int",
                      dest="percent", metavar="INTEGER",
                      help="percentage up to which the volume shall be filled")
    (options, args) = parser.parse_args()

    if not (args and len(args) > 0):
        parser.print_help()
        sys.exit(1)

    if options.debug:
        logging.basicConfig(level=logging.DEBUG)

    # Take action as specified on the command line.
    to_execute = args[0].lower()
    if to_execute == "test":
        try:
            global noverify
            if options.noverify:
                noverify = True
            else:
                noverify = False
            global test_folder
            if options.file:
            	test_folder = options.file
            else:
            	test_folder = test_folder_default
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(
                bbTest)
            unittest.TextTestRunner().run(suite)
        except SystemExit:
            pass
    elif to_execute == "wipe":
        if not options.file:
            parser.print_help()
            sys.exit(1)
        file_wipe(options.file)
    elif to_execute == "search":
        if not (options.file and options.search):
            parser.print_help()
            sys.exit(1)
        print("Searcing volume %s for string %s..." % (
            options.file, options.search))
        search_result = search_volume_for_string(
            options.file, options.search)
        print("Search result: %r" % search_result)
    elif to_execute == "fill":
        if not (options.file and options.percent):
            parser.print_help()
            sys.exit(1)
        fill_volume_to_pct(options.file, options.percent)
    else:
        parser.print_help()
