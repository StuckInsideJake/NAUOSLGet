"""
The email_parser program allows the user to connect to their inbox, find emails from the
relevant sender (intended to be emails from online version management tools about issues
opened in a given source code repository), parse those emails for identifying
characteristics (such as issue numbers, for example), send those identifiers to the repo
extractor for mining.
"""

import argparse
import email
from email import policy
import imaplib
import os
import re
from src import file_io


HOST_DICT = {
    "gmail": "imap.gmail.com",
    "outlook": "outlook.office365.com",
    "yahoo": "imap.mail.yahoo.com",
}

SENDER_DICT = {"github": '"Github"', "jira": '"Jira"'}


def main():
    """
    - Enabling Gmail
        - less secure apps: when using Gmail, you may need to allow "less secure apps"
          access to your account. See https://myaccount.google.com/lesssecureapps
    """
    # get configuration from JSON file as a dictionary
    print("\nReading parser configuration...")
    cfg_metadict = get_cfg_dict()

    # cfg should have both "parser" and "extractor" inner dicts. We want "parser" for
    # now
    parser_cfg = cfg_metadict["parser"]

    # get mail object encapsulating open connection to mailbox
    print("\nConnecting to user's inbox...")
    session = get_connection_obj(parser_cfg)

    # get a dictionary of email dates, subjects, and bodies
    sender = SENDER_DICT[parser_cfg["sender"]]
    repo = parser_cfg["repo"]
    print(f"\nSearching user's inbox for emails\n\tfrom {sender}\n\tabout {repo}...")
    email_content_dict = get_cleaned_email_dict(session, parser_cfg["sender"])

    # from email dictionary, derive a list of issue numbers to mine with the extractor
    issue_list = get_issue_num_list(email_content_dict, parser_cfg)
    print(f"\nIssues found in inbox to mine for:\n\t{issue_list}\n")

    issue_list = [int(issue_list[0]), int(issue_list[-1])]
    print(f"\nIssue range to mine: \n\t{issue_list}\n")

    # get list of lists of sequential issue number groupings to make extraction simpler
    # issue_grp_metalist = partition_issue_list(issue_list)

    # execute the extractor
    exe_extractor(cfg_metadict, issue_list)


def create_extractor_input(
    cfg_metadict: dict, issue_num_list: list, out_path: str
) -> None:
    """
    write a dictionary of configuration values to the filesystem (path designated in the
    input configuration file)

    :param cfg_metadict dict: dictionary of dictionaries of configuration values
    :rtype None
    """
    parser_cfg = cfg_metadict["parser"]

    extractor_cfg = cfg_metadict["extractor"]
    extractor_cfg |= {"repo": parser_cfg["repo"], "range": issue_num_list}

    file_io.write_dict_to_json(extractor_cfg, out_path)


def exe_extractor(cfg_metadict: dict, issue_list: list) -> None:
    """
    1. create dir in local fs to store email parser output/repo extractor input in
    2. for each group of sequential issue numbers:
        • generate a file name in the output path from #1 above
        • create extractor input using path and other information
        • execute call to extractor

    :param cfg_metadict dict: dictionary of dictionary of configurations for email
    parser
    :param issue_list list[int]: list of starting and ending issue numbers to mine
    between
    with the extractor
    :rtype None: executes call to repo extractor
    """
    parser_cfg = cfg_metadict["parser"]

    # create dir using name of repo to send new extractor input to
    output_dir = parser_cfg["output_dir"] + "/" + parser_cfg["repo"].rsplit("/", 1)[1]
    os.makedirs(output_dir, exist_ok=True)

    print(f"Creating extractor input JSON at {output_dir} ...\n")

    # create file name using index of sequential grouping of issue numbers
    cur_extractor_input = output_dir + "/extractor_input.json"

    # create a configuration file for running the extractor.
    # uses values from the configuration file and the issue numbers found by this
    # program
    create_extractor_input(cfg_metadict, issue_list, cur_extractor_input)

    # call extractor with newly-created configuration
    extractor_exe = parser_cfg["extractor_exe"]

    cur_exe_str = f"Calling extractor with {cur_extractor_input} ..."

    print(f"{cur_exe_str}\n{'-' * len(cur_exe_str)}\n")
    os.system(f"python {extractor_exe} {cur_extractor_input}")


def get_cfg_dict() -> dict:
    """
    get dict of cfg values from path to JSON cfg file

    :rtype dict: dictionary of configuration values
    """
    # establish positional argument capability
    arg_parser = argparse.ArgumentParser(description="NAU-OSL email parsing utility")

    arg_parser.add_argument(
        "json_cfg_path",
        type=str,
        help="Path to JSON file containing configuration values",
    )

    cfg_path = arg_parser.parse_args().json_cfg_path

    return file_io.read_json_to_dict(cfg_path)


def get_cleaned_email_dict(imap_session: imaplib.IMAP4_SSL, sender: str):
    """
    parent function that encapsulates the retrieval and cleaning of email data

    :param imap_session imaplib.IMAP4_SSL: active connection to imap server
    :param sender str: sender to look for emails from, e.g. GitHub, in the chosen
    inbox
    """
    # use list of message positions to get email objects
    email_obj_list = get_email_obj_list(imap_session, sender)

    # get dictionary of email dates, subjects, and bodies from list of email objects
    email_content_dict = get_email_content_dict(email_obj_list)

    # remove all unprintable chars from email bodies and turn into lists
    cleaned_email_content_dict = parse_email_bodies(email_content_dict)

    return cleaned_email_content_dict


def get_connection_obj(cfg_dict: dict) -> imaplib.IMAP4_SSL:
    """
    create connection to imap server using user-provided cfg values

    :param cfg_dict dict: dictionary of cfg values
    :rtype imaplib.IMAP4_SSL: imaplib object representing connection to imap server
    """

    imap_domain = HOST_DICT[cfg_dict["host"]]

    # init mail session
    mail = imaplib.IMAP4_SSL(imap_domain)

    # login; see note in doc about "less secure apps"
    mail.login(cfg_dict["addr"], cfg_dict["passwd"])

    # select mailbox and disallow writing to it
    mail.select(readonly=True)

    return mail


def get_email_content_dict(email_list: list) -> dict:
    """
    use list of email objects to create dictionary of content from emails

    :param email_list list: list of email objects
    :rtype dict: dictionary of contents from each email object in the param list of
    emails
    """
    email_content_dict = {}
    index = 0

    # for each email in the list of emails given as param
    for msg in email_list:

        # create and merge dict entry for current message
        email_content_dict |= {
            index: {
                "date": msg["Date"],
                "subject": msg["subject"],
                "body": msg.get_body("plain").get_content(),
            }
        }

        index += 1

    return email_content_dict


def get_email_obj_list(session: imaplib.IMAP4_SSL, sender_str: str) -> list:
    """
    create and return list of email objects from positions of emails in inbox

    :param session imaplib.IMAP4_SSL: object containing connection to user's imap server
    :param position_list list: list of integers representing positions of relevant
    emails in inbox
    :rtype list: list of email objects encapsulating emails of interest
    """
    email_obj_list = []

    # get list of positions of relevant emails in inbox as a string
    _, msg_pos_str_list = session.search(None, "FROM", SENDER_DICT[sender_str])

    # break string of email indices in inbox into a list
    email_position_list = msg_pos_str_list[0].split()

    for uid in email_position_list:

        # get that emails data
        _, email_data = session.fetch(uid, "(RFC822)")

        # if the data is not none
        if email_data[0] is not None:

            # get it's data as bytes
            _, msg_bytes = email_data[0]

            # get an email object from those bytes
            email_obj = email.message_from_bytes(
                bytes(msg_bytes), policy=policy.default
            )

            # put them into a list
            email_obj_list.append(email_obj)

    return email_obj_list


def get_issue_num_list(email_dict: dict, cfg_dict: dict) -> list:
    """
    depending on what domains we are looking for emails from, e.g. Jira, we need to use
    different regex to find the numbers of the new issues that have been created in the
    repository of interest. This function will look through the dictionary of email
    content that we have, find the emails that were sent to the user as a consequence of
    the creation of a new issue in the repo of interest, get the issue numbers from
    those emails, validate that those issue numbers are the ones we want to mine for by
    comparing them to the subject line of the email, then return the list of issue
    numbers to mine with the extractor.

    :param cfg_dict dict: dictionary of configuration values
    :param email_dict dict: dictionary of email content; date, subject, body for each
    :rtype list: list of issue numbers to mine with the extractor
    """

    cfg_repo = cfg_dict["repo"]
    cfg_sender = cfg_dict["sender"]
    body_list = []
    issue_list = []

    # remove any emails which are not about new issues
    if "github" in cfg_sender:
        # create url which indicates new issue created; f-string and regex
        subject_issue_str = r"\(Issue \#\d+\)"
        issue_url = rf"https://github.com/{cfg_repo}/issues/\d+$"

        # for every val in every key val pair in the dict of emails
        for entry in email_dict.values():

            # create list of issue numbers from urls resulting from issue creation.
            # When a new issue is created in github, a URL that has the form in the
            # variable above is sent out. We want the "\d+" part and get it via
            # rsplit if the url pattern is found in the list of body strings
            body_list = [
                string.rsplit("/", 1)[1]
                for string in entry["body"]
                if re.search(issue_url, string) is not None
            ]

            # The above process will search through the strings that compose the
            # body of the current email for URLs that match the pattern that GitHub
            # uses when sending emails which document the creation of a new issue.
            # If one is found, it is LIKELY that the email was sent as a consequence
            # of the creation of a new issue, but we want to make absolute certain
            # that the found URL actually isn't just a URL that happened to be
            # placed in the body by someone's comments. To do this, we are going to
            # compare the number found at the end of the URL to the number of the
            # issue in the subject, which has the form shown above.

            # if the list has an issue number (meaning that it was an email about
            # the creation of a new issue)
            if body_list:

                # get the label in the subject documenting what issue the email
                # pertains to
                subject_issue = re.search(subject_issue_str, entry["subject"])

                # if that label does exist
                if subject_issue is not None:

                    # get the issue number
                    issue_num = [
                        num for num in body_list if num in subject_issue.group()
                    ]

                    issue_list.append(*issue_num)

    elif "jira" in cfg_sender:
        pass

    else:
        pass

    return sorted(issue_list)


def parse_email_bodies(email_dict: dict) -> dict:
    """
    for each email in dictionary of found relevant emails, remove all unprintable chars
    from the email body and return the dictionary of emails

    :param email_dict dict: dictionary of relevant emails to return data of back to the
    user
    :rtype dict: dictionary of emails passed in as param, with bodies cleared of
    unprintable characters
    """
    for key in email_dict.keys():

        filtered_body_list = []
        filtered_body = ""

        # for each char in body of email at current key
        for char in email_dict[key]["body"]:

            # keep only printable chars.
            # this is really useful because modern email content is full of unprintable
            # characters
            if char.isprintable():
                filtered_body += char

            # otherwise, append all printable chars found above to list of body contents
            else:
                if filtered_body != "":
                    filtered_body_list.append(filtered_body)
                    filtered_body = ""

        # assign formatted body back to proper place in dictionary
        email_dict[key]["body"] = filtered_body_list

    return email_dict


# def partition_issue_list(issue_list: list) -> list[list]:
#     """
#     1. sorts list of issue numbers
#     2. iterates through and determines which groups are sequential
#     3. packages sequential groupings into lists
#     4. returns list of grouped sequential issue numbers
#
#     :param issue_list list: list of issue numbers from email parsing
#     :rtype list[list]: list of lists of ordered, sequential issue numbers to mine
#     """
#     cur_seq_group = [int(issue_list[0])]
#     i = 0
#     issue_num_metalist = []
#
#     # sort list to be sure of orderliness
#     issue_list.sort()
#
#     while i < len(issue_list) - 1:
#         pass
#
#         # cur_issue = int(issue_list[i])
#         # next_issue = int(issue_list[i + 1])
#
#         # print(f"current: {cur_issue}, next: {next_issue}\n")
#
#         # cur_seq_group.append(cur_issue)
#
#     #     # if the next issue is not the current issue number + 1, e.g. cur = 1,
#     #     # next = 3
#     #     if next_issue != cur_issue + 1 or next_i == len(issue_list) - 1:
#     #         # append current item to list as end of sequential range
#     #         cur_seq_group.append(cur_issue)
#
#     #         # append current grouping of sequential values to the metalist of values
#     #         issue_num_metalist.append(cur_seq_group)
#
#     #         # restart list of sequential groupings, starting at the value that broke
#     #         # the current sequential grouping
#     #         cur_seq_group = [next_issue]
#
#     #     i += 1
#
#     return issue_num_metalist


if __name__ == "__main__":
    main()