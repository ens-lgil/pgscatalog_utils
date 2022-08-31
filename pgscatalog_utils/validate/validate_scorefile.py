import os, glob, re
import argparse
from xmlrpc.client import boolean

data_sum = {'valid': [], 'invalid': [], 'other': []}

val_types = ('formatted', 'hm_pos')


def read_last_line(file: str) -> str:
    '''
    Return the last line of the file
    '''
    fileHandle = open ( file,"r" )
    lineList = fileHandle.readlines()
    fileHandle.close()
    return lineList[-1]


def file_validation_state(filename: str, log_file: str) -> None:
    global data_sum
    if os.path.exists(log_file):
        log_result = read_last_line(log_file)
        if re.search("File is valid", log_result):
            print("> valid\n")
            data_sum['valid'].append(filename)
        elif re.search("File is invalid", log_result):
            print("#### invalid! ####\n")
            data_sum['invalid'].append(filename)
        else:
            print("!! validation process had an issue. Please look at the logs.\n")
            data_sum['other'].append(filename)
    else:
        print("!! validation process had an issue: the log file can't be found")
        data_sum['other'].append(filename)


def validate_file(filepath: str, log_dir: str, score_dir: str, main_validator: object, check_filename: boolean) -> None:
    file = os.path.basename(filepath)
    filename = file.split('.')[0]
    print("Filename: "+file)
    log_file = log_dir+'/'+filename+'_log.txt'

    # Run validator
    main_validator.run_validator(filepath,check_filename,log_file,score_dir)

    # Check log
    file_validation_state(file,log_file)



def main():
    global data_sum

    argparser = argparse.ArgumentParser()
    argparser.add_argument("-t", help=f"Type of validator: {' or '.join(val_types)}", metavar='VALIDATOR_TYPE')
    argparser.add_argument("-f", help='The path to the polygenic scoring file to be validated (no need to use the [--dir] option)', metavar='SCORING_FILE_NAME')
    argparser.add_argument('--dir', help='The name of the directory containing the files that need to processed (no need to use the [-f] option')
    argparser.add_argument('--score_dir', help='The name of the directory containing the formatted scoring files to compare with harmonized scoring files (optional)')
    argparser.add_argument('--log_dir', help='The name of the log directory where the log file(s) will be stored', required=True)
    argparser.add_argument('--check_filename', help='Check that the file name match the PGS Catalog nomenclature', required=False, action='store_true')

    args = argparser.parse_args()

    score_dir = None
    check_filename = False

    validator_type = args.t
    files_dir = args.dir
    log_dir = args.log_dir

    # Type of validator
    if validator_type not in val_types:
        print(f"Error: Validator type (option -t) '{validator_type}' is not in the list of recognized types: {val_types}.")
        exit(1)
    # Logs dir
    if not os.path.isdir(log_dir):
        print(f"Error: Log dir '{log_dir}' can't be found!")
        exit(1)
    # File(s) directory
    if args.f and files_dir:
        print("Error: you can't use both options [-f] - single scoring file and [--dir] - directory of scoring files. Please use only 1 of these 2 options!")
        exit(1)
    # File path
    if not args.f and not files_dir:
        print("Error: you need to provide a scoring file [-f] or a directory of scoring files [--dir]!")
        exit(1)
    # Scoring files directory (only to compare with the harmonized files)
    if args.score_dir:
        score_dir = args.score_dir
        if not os.path.isdir(score_dir):
            print(f"Error: Scoring file directory '{score_dir}' can't be found!")
            exit(1)
    elif validator_type != 'formatted':
            print("WARNING: the parameter '--score_dir' is not present in the submitted command line, therefore the comparison of the number of data rows between the formatted scoring file(s) and the harmonized scoring file(s) won't be performed.")
    # Check PGS Catalog file name nomenclature
    if args.check_filename:
        check_filename = True
    else:
        print("WARNING: the parameter '--check_filename' is not present in the submitted command line, therefore the validation of the scoring file name(s) won't be performed.")



    # Select validator:
    if validator_type == 'formatted':
        import pgscatalog_utils.validate.formatted.validator as main_validator
    elif validator_type == 'hm_pos':
        import pgscatalog_utils.validate.harmonized_position.validator as main_validator

    # One file
    if args.f:
        if os.path.isfile(args.f):
            validate_file(args.f,log_dir,score_dir,main_validator,check_filename)
        else:
            print(f"Error: Scoring file '{args.f}' can't be found!")
            exit(1)

    # Content of the directory
    elif files_dir:
        if os.path.isdir(files_dir):
            count_files = 0
            # Browse directory: for each file run validator
            for filepath in sorted(glob.glob(files_dir+"/*.*")):
                validate_file(filepath,log_dir,score_dir,main_validator,check_filename)
                count_files += 1

            # Print summary  + results
            print("\nSummary:")
            if data_sum['valid']:
                print("- Valid: "+str(len(data_sum['valid']))+"/"+str(count_files))
            if data_sum['invalid']:
                print("- Invalid: "+str(len(data_sum['invalid']))+"/"+str(count_files))
            if data_sum['other']:
                print("- Other issues: "+str(len(data_sum['other']))+"/"+str(count_files))

            if data_sum['invalid']:
                print("Invalid files:")
                print("\n".join(data_sum['invalid']))

        # Directory doesn't exist
        elif not os.path.isdir(files_dir):
            print(f"Error: the scoring file directory '{files_dir}' can't be found!")

if __name__ == '__main__':
    main()
