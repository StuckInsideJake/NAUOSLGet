"""The io module provides I/O functionality to the Extractor class"""

import json
from json.decoder import JSONDecodeError
import sys


def read_json_to_dict(in_path: str) -> dict:
    """
    open the provided JSON file and read its contents out into a dictionary

    :raises FileNotFoundError: file does not exist at path
    :param cfg_file str: path name to a JSON configuration file
    :rtype dict: dictionary constructed from JSON string
    """

    try:
        with open(in_path, "r", encoding="UTF-8") as file_obj:
            json_text = file_obj.read()

    except FileNotFoundError:
        print(f"\nFile at {in_path} not found!")
        sys.exit(1)

    else:
        return json.loads(json_text)


def read_txt_line(in_path: str) -> str:
    """
    read a single line from the top of a text file.
    Used for reading personal access tokens (PATs) out of auth file

    :raises FileNotFoundError: file does not exist at path
    :param auth_file_path str: path to auth file
    :rtype pat_list list[str]: text lines from auth file
    """
    try:
        with open(in_path, "r", encoding="UTF-8") as file_obj:
            file_text = file_obj.readline()

    except FileNotFoundError:
        # if the file is not found log an error and exit
        print(f"\nFile at {in_path} not found!")
        sys.exit(1)

    else:
        return file_text.strip().strip("\n")


def write_dict_to_json(out_dict: dict, out_path: str) -> None:
    """
    write given Python dictionary to output file as JSON

    :raises FileNotFoundError: file does not exist at path
    :param out_dict dict: dictionary to write as JSON
    :param out_path str: path to write output to
    :rtype None
    """
    try:
        with open(out_path, "w", encoding="UTF-8") as json_outfile:
            json.dump(out_dict, json_outfile, ensure_ascii=False, indent=4)

    except FileNotFoundError:
        print(f"\nFile at {out_path} not found!")


def write_merged_dict_to_json(out_dict: dict, out_path: str) -> None:
    """
    gets the desired output path, opens and reads any JSON data that may already be
    there, and recursively merges in param data from the most recent round of API
    calls

    :param out_dict dict[unknown]: dict of data from round of API calls to merge and
    write
    :param out_path str: path to file in fs that we want to write to

    :rtype None: writes output to file, nothing returned
    """

    def __merge_dicts_recursive(add_dict, base_dict) -> None:
        """
        loops through keys in dictionary of data from round of API calls to merge
        their data into existing JSON data

        credit to Paul Durivage: https://gist.github.com/angstwad/bf22d1822c38a92ec0a9

        :param add_dict dict[unknown]: dict of data to be written

        :param base_dict dict[unknown]: dict of data already written to and read out
        from JSON file

        :rtype None: merges param dicts
        """
        # for each key in the dict that we created with the round of API calls
        for key in add_dict:

            # if that key is in the dict in the existing JSON file and the val at
            # the key is a dict in both dictionaries
            if (
                key in base_dict
                and isinstance(base_dict[key], dict)
                and isinstance(add_dict[key], dict)
            ):
                # recurse
                __merge_dicts_recursive(add_dict[key], base_dict[key])

            else:
                # assign the new value from the last round of calls to the existing
                # key
                base_dict[key] = add_dict[key]

    json_dict = {}

    # attempt to read JSON out of output file
    try:
        json_dict = read_json_to_dict(out_path)

    # if no JSON content exists there, ignore. In this context, it simply means that we
    # are writing JSON to a new file
    except JSONDecodeError:
        pass

    # in any case
    finally:
        # recursively merge all dicts and nested dicts in both dictionaries
        __merge_dicts_recursive(out_dict, json_dict)

        # write JSON content back to file
        write_dict_to_json(json_dict, out_path)

    print()