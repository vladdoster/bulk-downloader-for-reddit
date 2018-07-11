#!/usr/bin/env python

"""
This program downloads imgur, gfycat and direct image and video links of 
saved posts from a reddit account. It is written in Python 3.
"""

import argparse
import os
import sys
import time
from pathlib import Path, PurePath

from src.downloader import Direct, Gfycat, Imgur, Self
from src.parser import LinkDesigner
from src.searcher import getPosts
from src.tools import (GLOBAL, createLogFile, jsonFile, nameCorrector,
                       printToFile)
from src.errors import *

__author__ = "Ali Parlakci"
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Ali Parlakci"
__email__ = "parlakciali@gmail.com"

def getConfig(configFileName):
    """Read credentials from config.json file"""

    keys = ['imgur_client_id',
            'imgur_client_secret']

    if os.path.exists(configFileName):
        FILE = jsonFile(configFileName)
        content = FILE.read()
        if "reddit_refresh_token" in content:
            if content["reddit_refresh_token"] == "":
                FILE.delete("reddit_refresh_token")
        for key in keys:
            try:
                if content[key] == "":
                    raise KeyError
            except KeyError:
                print(key,": ")
                FILE.add({key:input()})
        return jsonFile(configFileName).read()

    else:
        FILE = jsonFile(configFileName)
        configDictionary = {}
        for key in keys:
            configDictionary[key] = input(key + ": ")
        FILE.add(configDictionary)
        return FILE.read()

def parseArguments(arguments=[]):
    """Initialize argparse and add arguments"""

    parser = argparse.ArgumentParser(allow_abbrev=False,
                                     description="This program downloads " \
                                                 "media from reddit " \
                                                 "posts")
    parser.add_argument("--directory",
                        help="Specifies the directory where posts will be " \
                        "downloaded to",
                        metavar="DIRECTORY")

    parser.add_argument("--link","-l",
                        help="Get posts from link",
                        metavar="link")

    parser.add_argument("--saved",
                        action="store_true",
                        help="Triggers saved mode")

    parser.add_argument("--submitted",
                        action="store_true",
                        help="Gets posts of --user")

    parser.add_argument("--upvoted",
                        action="store_true",
                        help="Gets upvoted posts of --user")

    parser.add_argument("--log",
                        help="Triggers log read mode and takes a log file",
                        # type=argparse.FileType('r'),
                        metavar="LOG FILE")

    parser.add_argument("--subreddit",
                        nargs="+",
                        help="Triggers subreddit mode and takes subreddit's " \
                             "name without r/. use \"frontpage\" for frontpage",
                        metavar="SUBREDDIT",
                        type=str)
    
    parser.add_argument("--multireddit",
                        help="Triggers multireddit mode and takes "\
                             "multireddit's name without m/",
                        metavar="MULTIREDDIT",
                        type=str)

    parser.add_argument("--user",
                        help="reddit username if needed. use \"me\" for " \
                             "current user",
                        required="--multireddit" in sys.argv or \
                                 "--submitted" in sys.argv,
                        metavar="redditor",
                        type=str)

    parser.add_argument("--search",
                        help="Searches for given query in given subreddits",
                        metavar="query",
                        type=str)

    parser.add_argument("--sort",
                        help="Either hot, top, new, controversial, rising " \
                             "or relevance default: hot",
                        choices=[
                            "hot","top","new","controversial","rising",
                            "relevance"
                        ],
                        metavar="SORT TYPE",
                        type=str)

    parser.add_argument("--limit",
                        help="default: unlimited",
                        metavar="Limit",
                        type=int)

    parser.add_argument("--time",
                        help="Either hour, day, week, month, year or all." \
                             " default: all",
                        choices=["all","hour","day","week","month","year"],
                        metavar="TIME_LIMIT",
                        type=str)
    
    parser.add_argument("--NoDownload",
                        help="Just gets the posts and store them in a file" \
                             " for downloading later",
                        action="store_true",
                        default=False)

    if arguments == []:
        return parser.parse_args()
    else:
        return parser.parse_args(arguments)

def checkConflicts():
    """Check if command-line arguments are given correcly,
    if not, raise errors
    """

    if GLOBAL.arguments.user is None:
        user = 0
    else:
        user = 1

    modes = ["saved","subreddit","submitted","search","log","link","upvoted"]

    values = {x: 0 if x is None or x is False else 1 for x in modes}

    if not sum(values[x] for x in values) == 1:
        print("Program mode is invalid")
        quit()
    
    if values["search"]+values["saved"] == 2:
        print("You cannot search in your saved posts")
        quit()

    if values["search"]+values["submitted"] == 2:
        print("You cannot search in submitted posts")
        quit()

    if values["search"]+values["upvoted"] == 2:
        print("You cannot search in upvoted posts")
        quit()

    if values["upvoted"]+values["submitted"] == 1 and user == 0:
        print("No redditor name given")
        quit()

class PromptUser:
    @staticmethod
    def chooseFrom(choices):
        print()
        choicesByIndex = list(str(x) for x in range(len(choices)+1))
        for i in range(len(choices)):
            print("{indent}[{order}] {mode}".format(
                indent=" "*4,order=i+1,mode=choices[i]
            ))
        print(" "*4+"[0] exit\n")
        choice = input("> ")
        while not choice.lower() in choices+choicesByIndex:
            print("Invalid input\n")
            programModeIndex = input("> ")

        if choice == "0":
            quit()
        elif choice in choicesByIndex:
            return choices[int(choice)-1]
        else:
            return choice
    
    def __init__(self):
        print("select program mode:")
        programModes = [
            "search","subreddit","multireddit",
            "submitted","upvoted","saved","log"
        ]
        programMode = self.chooseFrom(programModes)

        if programMode == "search":
            GLOBAL.arguments.search = input("\nquery: ")
            GLOBAL.arguments.subreddit = input("\nsubreddit: ")

            print("\nselect sort type:")
            sortTypes = [
                "relevance","top","new"
            ]
            sortType = self.chooseFrom(sortTypes)
            GLOBAL.arguments.sort = sortType

            print("\nselect time filter:")
            timeFilters = [
                "hour","day","week","month","year","all"
            ]
            timeFilter = self.chooseFrom(timeFilters)
            GLOBAL.arguments.time = timeFilter

        if programMode == "subreddit":
            GLOBAL.arguments.subreddit = input("\nsubreddit: ")
            if " " in GLOBAL.arguments.subreddit:
                GLOBAL.arguments.subreddit = "+".join(GLOBAL.arguments.subreddit.split())

            print("\nselect sort type:")
            sortTypes = [
                "hot","top","new","rising","controversial"
            ]
            sortType = self.chooseFrom(sortTypes)
            GLOBAL.arguments.sort = sortType

            if sortType in ["top","controversial"]:
                print("\nselect time filter:")
                timeFilters = [
                    "hour","day","week","month","year","all"
                ]
                timeFilter = self.chooseFrom(timeFilters)
                GLOBAL.arguments.time = timeFilter
            else:
                GLOBAL.arguments.time = "all"

        elif programMode == "multiredit":
            GLOBAL.arguments.user = input("\nredditor: ")
            GLOBAL.arguments.subreddit = input("\nmultireddit: ")
            
            print("\nselect sort type:")
            sortTypes = [
                "hot","top","new","rising","controversial"
            ]
            sortType = self.chooseFrom(sortTypes)
            GLOBAL.arguments.sort = sortType

            if sortType in ["top","controversial"]:
                print("\nselect time filter:")
                timeFilters = [
                    "hour","day","week","month","year","all"
                ]
                timeFilter = self.chooseFrom(timeFilters)
                GLOBAL.arguments.time = timeFilter
            else:
                GLOBAL.arguments.time = "all"
        
        elif programMode == "submitted":
            GLOBAL.arguments.submitted = True
            GLOBAL.arguments.user = input("\nredditor: ")
        
        elif programMode == "upvoted":
            GLOBAL.arguments.upvoted = True
            GLOBAL.arguments.user = input("\nredditor: ")
        
        elif programMode == "saved":
            GLOBAL.arguments.saved = True
            GLOBAL.arguments.user = input("\nredditor: ")
        
        elif programMode == "log":
            GLOBAL.arguments.log = input("\nlog file directory:")

        GLOBAL.arguments.limit = int(input("\nlimit: "))

def prepareAttributes():
    ATTRIBUTES = {}

    if GLOBAL.arguments.user is not None:
        ATTRIBUTES["user"] = GLOBAL.arguments.user

    if GLOBAL.arguments.search is not None:
        ATTRIBUTES["search"] = GLOBAL.arguments.search
        if GLOBAL.arguments.sort == "hot" or \
           GLOBAL.arguments.sort == "controversial" or \
           GLOBAL.arguments.sort == "rising":
            GLOBAL.arguments.sort = "relevance"

    if GLOBAL.arguments.sort is not None:
        ATTRIBUTES["sort"] = GLOBAL.arguments.sort
    else:
        if GLOBAL.arguments.submitted:
            ATTRIBUTES["sort"] = "new"
        else:
            ATTRIBUTES["sort"] = "hot"

    if GLOBAL.arguments.time is not None:
        ATTRIBUTES["time"] = GLOBAL.arguments.time
    else:
        ATTRIBUTES["time"] = "all"

    if GLOBAL.arguments.link is not None:

        GLOBAL.arguments.link = GLOBAL.arguments.link.strip("\"")

        try:
            ATTRIBUTES = LinkDesigner(GLOBAL.arguments.link)
        except InvalidRedditLink:
            raise InvalidRedditLink

        if GLOBAL.arguments.search is not None:
            ATTRIBUTES["search"] = GLOBAL.arguments.search

        if GLOBAL.arguments.sort is not None:
            ATTRIBUTES["sort"] = GLOBAL.arguments.sort

        if GLOBAL.arguments.time is not None:
            ATTRIBUTES["time"] = GLOBAL.arguments.time

    elif GLOBAL.arguments.subreddit is not None:
        if type(GLOBAL.arguments.subreddit) == list:    
            GLOBAL.arguments.subreddit = "+".join(GLOBAL.arguments.subreddit)

        ATTRIBUTES["subreddit"] = GLOBAL.arguments.subreddit

    elif GLOBAL.arguments.saved is True:
        ATTRIBUTES["saved"] = True

    elif GLOBAL.arguments.upvoted is True:
        ATTRIBUTES["upvoted"] = True

    elif GLOBAL.arguments.submitted is not None:
        ATTRIBUTES["submitted"] = True

        if GLOBAL.arguments.sort == "rising":
            raise InvalidSortingType
    
    ATTRIBUTES["limit"] = GLOBAL.arguments.limit

    return ATTRIBUTES

def postFromLog(fileName):
    """Analyze a log file and return a list of dictionaries containing
    submissions
    """
    if Path.is_file(Path(fileName)):
        content = jsonFile(fileName).read()
    else:
        print("File not found")
        quit()

    try:
        del content["HEADER"]
    except KeyError:
        pass

    posts = []

    for post in content:
        if not content[post][-1]['postType'] == None:
            posts.append(content[post][-1])

    return posts

def postExists(POST):
    """Figure out a file's name and checks if the file already exists"""

    title = nameCorrector(POST['postTitle'])
    FILENAME = title + "_" + POST['postId']
    PATH = GLOBAL.directory / POST["postSubreddit"]
    possibleExtensions = [".jpg",".png",".mp4",".gif",".webm",".md"]

    for i in range(2):
        for extension in possibleExtensions:
            FILE_PATH = PATH / (FILENAME+extension)
            if FILE_PATH.exists():
                return True
        else:
            FILENAME = POST['postId']
    else:
        return False

def download(submissions):
    """Analyze list of submissions and call the right function
    to download each one, catch errors, update the log files
    """

    subsLenght = len(submissions)
    lastRequestTime = 0
    downloadedCount = subsLenght
    duplicates = 0
    BACKUP = {}

    FAILED_FILE = createLogFile("FAILED")

    for i in range(subsLenght):
        print("\n({}/{})".format(i+1,subsLenght))
        print(
            "https://reddit.com/r/{subreddit}/comments/{id}".format(
                subreddit=submissions[i]['postSubreddit'],
                id=submissions[i]['postId']
            )
        )

        if postExists(submissions[i]):
            result = False
            print(submissions[i]['postType'].upper())
            print("It already exists")
            duplicates += 1
            downloadedCount -= 1
            continue

        directory = GLOBAL.directory / submissions[i]['postSubreddit']

        if submissions[i]['postType'] == 'imgur':
            print("IMGUR",end="")
            
            while int(time.time() - lastRequestTime) <= 2:
                pass
            credit = Imgur.get_credits()

            IMGUR_RESET_TIME = credit['UserReset']-time.time()
            USER_RESET = ("after " \
                          + str(int(IMGUR_RESET_TIME/60)) \
                          + " Minutes " \
                          + str(int(IMGUR_RESET_TIME%60)) \
                          + " Seconds") 
            print(
                " => Client: {} - User: {} - Reset {}".format(
                    credit['ClientRemaining'],
                    credit['UserRemaining'],
                    USER_RESET
                )
            )

            if not (credit['UserRemaining'] == 0 or \
                    credit['ClientRemaining'] == 0):

                """This block of code is needed
                """
                while int(time.time() - lastRequestTime) <= 2:
                    pass
                lastRequestTime = time.time()

                try:
                    Imgur(directory,submissions[i])

                except FileAlreadyExistsError:
                    print("It already exists")
                    duplicates += 1
                    downloadedCount -= 1

                except ImgurLoginError:
                    print(
                        "Imgur login failed. Quitting the program "\
                        "as unexpected errors might occur."
                    )
                    quit()

                except Exception as exception:
                    print(exception)
                    FAILED_FILE.add({int(i+1):[str(exception),submissions[i]]})
                    downloadedCount -= 1

            else:
                if credit['UserRemaining'] == 0:
                    KEYWORD = "user"
                elif credit['ClientRemaining'] == 0:
                    KEYWORD = "client"

                print('{} LIMIT EXCEEDED\n'.format(KEYWORD.upper()))
                FAILED_FILE.add(
                    {int(i+1):['{} LIMIT EXCEEDED\n'.format(KEYWORD.upper()),
                               submissions[i]]}
                )
                downloadedCount -= 1

        elif submissions[i]['postType'] == 'gfycat':
            print("GFYCAT")
            try:
                Gfycat(directory,submissions[i])

            except FileAlreadyExistsError:
                print("It already exists")
                duplicates += 1
                downloadedCount -= 1
                
            except NotADownloadableLinkError as exception:
                print("Could not read the page source")
                FAILED_FILE.add({int(i+1):[str(exception),submissions[i]]})
                downloadedCount -= 1

            except Exception as exception:
                print(exception)
                FAILED_FILE.add({int(i+1):[str(exception),submissions[i]]})
                downloadedCount -= 1

        elif submissions[i]['postType'] == 'direct':
            print("DIRECT")
            try:
                Direct(directory,submissions[i])

            except FileAlreadyExistsError:
                print("It already exists")
                downloadedCount -= 1
                duplicates += 1

            except Exception as exception:
                print(exception)
                FAILED_FILE.add({int(i+1):[str(exception),submissions[i]]})
                downloadedCount -= 1
        
        elif submissions[i]['postType'] == 'self':
            print("SELF")
            try:
                Self(directory,submissions[i])

            except FileAlreadyExistsError:
                print("It already exists")
                downloadedCount -= 1
                duplicates += 1

            except Exception as exception:
                print(exception)
                FAILED_FILE.add({int(i+1):[str(exception),submissions[i]]})
                downloadedCount -= 1

        else:
            print("No match found, skipping...")
            downloadedCount -= 1

    if duplicates:
        print("\n There was {} duplicates".format(duplicates))

    if downloadedCount == 0:
        print(" Nothing downloaded :(")

    else:
        print(" Total of {} links downloaded!".format(downloadedCount))

def main():
    GLOBAL.arguments = parseArguments()

    if GLOBAL.arguments.directory is not None:
        GLOBAL.directory = Path(GLOBAL.arguments.directory)
    else:
        GLOBAL.directory = Path(input("download directory: "))

    if len(sys.argv) == 1:
        PromptUser()
    else:
        checkConflicts()

    GLOBAL.config = getConfig("config.json")

    print(sys.argv)

    if GLOBAL.arguments.log is not None:
        logDir = Path(GLOBAL.arguments.log)
        download(postFromLog(logDir))
        quit()

    try:
        POSTS = getPosts(prepareAttributes())
    except InsufficientPermission:
        print("You do not have permission to do that")
        quit()
    except NoMatchingSubmissionFound:
        print("No matching submission was found")
        quit()
    except NoRedditSupoort:
        print("Reddit does not support that")
        quit()
    except NoPrawSupport:
        print("PRAW does not support that")
        quit()
    except MultiredditNotFound:
        print("Multireddit not found")
        quit()
    except InvalidSortingType:
        print("Invalid sorting type has given")
        quit()
    except InvalidRedditLink:
        print("Invalid reddit link")
        quit()

    if POSTS is None:
        print("I could not find any posts in that URL")
        quit()

    if GLOBAL.arguments.NoDownload:
        quit()

    else:
        download(POSTS)

if __name__ == "__main__":
    try:
        VanillaPrint = print
        print = printToFile
        GLOBAL.RUN_TIME = time.time()
        main()
    except KeyboardInterrupt:
        print("\nQUITTING...")
        quit()
