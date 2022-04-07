"""
This module is intended to provide easy access to the extractor's
    1. getter functionality
    2. command dispatch tables
    3. configuration schema

    so that a user may be able to have an easier time adding functionality for
    their own uses, such as adding a new getter function.

To add a new piece of functionality, the user has to make a few modifications:
    1. create a new getter function which accesses items provided by PyGithub
    2. add that function to the appropriate subdictionary in the command
       dispatch table: {"field name to access function": function reference }
        • this allows the configuration schema to know which fields are
          acceptable

    You *do not* need to modify the schema to add a new getter. You *only* need
    to create the function and add it to the dispatch table in the appropriate
    item subdictionary.

Resources:
    • PyGithub documentation:
        https://pygithub.readthedocs.io/en/latest/github.html?highlight=main

    • See cerberus documentation for schema rules:
        https://docs.python-cerberus.org/en/stable/index.html

    • introduction to dispatch tables:
        https://betterprogramming.pub/dispatch-tables-in-python-d37bcc443b0b
"""

TIME_FMT = "%D, %I:%M:%S %p"


def _clean_str(str_to_clean) -> str:
    """
    If a string is empty or None, returns NaN. Otherwise, strip the string of any
    carriage returns, newlines, and leading or trailing whitespace.

    :param str_to_clean str: string to clean and return
    """
    if str_to_clean is None or str_to_clean == "":
        return "Nan"

    output_str = str_to_clean.replace("\r", "")
    output_str = output_str.replace("\n", "")

    return output_str.strip()


def _get_body(api_obj) -> str:
    """
    return issue or PR text body

    :param api_obj github.PullRequest/github.Issue: API object to get body text of
    """
    return _clean_str(api_obj.body)


def _get_commit_author_name(api_obj) -> str:
    return api_obj.commit.author.name


def _get_commit_committer(api_obj) -> str:
    return api_obj.commit.committer.name


def _get_commit_date(api_obj) -> str:
    return api_obj.commit.author.date.strftime(TIME_FMT)


def _get_commit_files(api_obj) -> dict:
    """
    For the list of files modified by a commit on a PR, return a list of qualities

    :param api_obj PaginatedList: paginated list of commits

    NOTE:
        If a list of files is too large, it will be returned as a paginatied
        list. See note about the list length constraints at
        https://docs.github.com/en/rest/reference/commits#get-a-commit. As of right
        now, this situation is not handled here.

    :rtype dict[unknown]: dictionary of fields discussing file attributes of a
    commit
    """
    file_list = api_obj.files

    commit_file_list = []
    commit_adds = 0
    commit_changes = 0
    commit_patch_text = ""
    commit_removes = 0
    commit_status_str = ""

    for file in file_list:
        commit_file_list.append(file.filename)
        commit_adds += int(file.additions)
        commit_changes += int(file.changes)
        commit_patch_text += str(file.patch) + ", "
        commit_removes += int(file.deletions)
        commit_status_str += str(file.status) + ", "

    quoted_commit_status_str = '"' + commit_status_str + '"'

    return {
        "file_list": commit_file_list,
        "additions": commit_adds,
        "changes": commit_changes,
        "patch_text": _clean_str(commit_patch_text),
        "removals": commit_removes,
        "status": _clean_str(quoted_commit_status_str),
    }


def _get_commit_msg(api_obj) -> str:
    return _clean_str(api_obj.commit.message)


def _get_commit_sha(api_obj) -> str:
    return api_obj.sha


def _get_closed_time(api_obj) -> str:
    """
    if the API object has been closed, i.e. closed PR or issue, return the formatted
    datetime that it was closed at

    :param api_obj github.PullRequest/github.Issue: API object to get datetime of
    closing of
    """
    if api_obj.closed_at is not None:
        return api_obj.closed_at.strftime(TIME_FMT)

    return "NaN"


def _get_issue_comments_discussants(comment_obj) -> dict:

    # TODO: lists are unhashable, meaning that, if we want a list of data about
    # discussants, we cannot simply put those lists in a set and return it. We
    # will need another way to remove non-unique identities from the list

    discussant_dict = {
        "id": _get_userid(comment_obj),
        "name": _get_username(comment_obj),
        "username": _get_userlogin(comment_obj),
    }

    return discussant_dict


def _get_issue_comments_quant(issue_obj):
    return issue_obj.comments


def _get_title(api_obj) -> str:
    return api_obj.title


def _get_userid(api_obj) -> str:
    return str(api_obj.user.id)


def _get_userlogin(api_obj) -> str:
    return _clean_str(api_obj.user.login)


def _get_username(api_obj) -> str:
    return _clean_str(api_obj.user.name)


# Initialize map of strings to function references, a dispatch table.
# This allows us to call a function using a string by saying
#
#           cmd_tbl_dict[type][function name]()
#
# To get an issue body, for example, we can either say
#
#           cmd_tbl_dict["issue"]["body"]()
#
# or we can store the subdictionary as a variable first
#
#           issue_fn_dict = cmd_tbl_dict["issue"])
#
# and then call from that subdictionary like
#
#           issue_fn_dict["body"]()
#
# We peform this exact method in the Extractor class getters
cmd_tbl_dict = {
    "commit": {
        "commit_author_name": _get_commit_author_name,
        "committer": _get_commit_committer,
        "commit_date": _get_commit_date,
        "commit_files": _get_commit_files,
        "commit_message": _get_commit_msg,
        "commit_sha": _get_commit_sha,
    },
    "issue": {
        "body": _get_body,
        "closed": _get_closed_time,
        "num_comments": _get_issue_comments_quant,
        "title": _get_title,
        "userlogin": _get_userlogin,
        "username": _get_username,
    },
    "issue_comment": {
        "body": _get_body,
        "discussant": _get_issue_comments_discussants,
    },
    "pr": {},
}


# Schema used to validate user-provided configuration. This acts as a template
# to judge whether the user cfg is acceptable to the program. This *does not*
# need to be modified to add new getter functionality
cfg_schema = {
    "repo": {"type": "string"},
    "auth_file": {"type": "string"},
    "state": {"allowed": ["closed", "open"], "type": "string"},
    "range": {"min": [0, 0], "schema": {"type": "integer"}, "type": "list"},
    "commit_fields": {
        "allowed": [*cmd_tbl_dict["commit"]],
        "schema": {"type": "string"},
        "type": "list",
    },
    "issue_comment_fields": {
        "allowed": [*cmd_tbl_dict["issue_comment"]],
        "schema": {"type": "string"},
        "type": "list",
    },
    "issue_fields": {
        "allowed": [*cmd_tbl_dict["issue"]],
        "schema": {"type": "string"},
        "type": "list",
    },
    "pr_fields": {
        "allowed": [*cmd_tbl_dict["pr"]],
        "schema": {"type": "string"},
        "type": "list",
    },
    "output_dir": {"type": "string"},
}
