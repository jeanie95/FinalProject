import requests
import json
from bs4 import BeautifulSoup
import secrets
from requests_oauthlib import OAuth1
import codecs
import sys
import re
from abc import ABCMeta, abstractmethod
from json import JSONDecodeError
import logging as log
import bs4
import http.client
import urllib
from yelpapi import YelpAPI

class InstagramUser:
    def __init__ (self, user_id, username = None, bio = None, followers_count=None, following_count =None, is_private =False):
        self.id =user_id
        self.username =username
        self.bio = bio
        self.followers_count = followers_count
        self.following_count = following_count
        self.is_private = is_private

class InstagramPost:
    def __init__(self,post_id,code,user=None,caption="", display_src=None,is_video=False,created_at=None):
        self.post_id = post_id
        self.code =code
        self.caption = caption
        self.user = user
        self.display_src = display_src
        self.is_video = is_video
        self.created_at = created_at

    def processed_text(self):
        if self.caption is None:
            return ""
        else:
            text = re.sub('[\n\r]',' ', self.caption)
            return text

    def hashtags(self):
        hashtags = []
        if self.caption is None:
            return hashtags
        else:
            for tag in re.findall("#[a-zA-Z0-9]+", self.caption):
                hashtags.append(tag)
            return hashtags

class HashTagSearch(metaclass =ABCMeta):
    instagram_root = "https://www.instagram.com"
    def __init__(self, ):
        super().__init__()

    def extract_recent_tag(self,tag):
        url_string = "https://www.instagram.com/explore/tags/%s/" % tag
        response = bs4.BeautifulSoup(requests.get(url_string).text, "html.parser")
        potential_query_ids = self.get_query_id(response)
        shared_data = self.extract_shared_data(response)

        media = shared_data['entry_data']['TagPage'][0]['graphql']['hashtag']['edge_hashtag_to_media']['edges']

        posts = []
        for node in media:
            post = self.extract_recent_instagram_post(node['node'])
            posts.append(post)
        self.save_results(posts)

        end_cursor = shared_data['entry_data']['TagPage'][0]['graphql']['hashtag']['edge_hashtag_to_media']['page_info']['end_cursor']


        success = False
        print(potential_query_ids)
        for potential_id in potential_query_ids:
            variables = {
                'tag_name': tag,
                'first': 4,
                'after': end_cursor
            }
            url = "https://www.instagram.com/graphql/query/?query_hash=%s&variables=%s" % (potential_id, json.dumps(variables))
            try:
                data = requests.get(url).json()
                if data['status'] == 'fail':

                    continue
                query_id = potential_id
                success = True
                break
            except JSONDecodeError as de:
                pass
        if not success:
            log.error("Error extracting Query Id, exiting")
            sys.exit(1)

        while end_cursor is not None:
            url = "https://www.instagram.com/graphql/query/?query_hash=%s&tag_name=%s&first=12&after=%s" % (
                query_id, tag, end_cursor)
            data = json.loads(requests.get(url).text)
            end_cursor = data['data']['hashtag']['edge_hashtag_to_media']['page_info']['end_cursor']
            posts = []
            for node in data['data']['hashtag']['edge_hashtag_to_media']['edges']:
                posts.append(self.extract_recent_query_instagram_post(node['node']))
            self.save_results(posts)

    def extract_shared_data(doc):
        for script_tag in doc.find_all("script"):
            if script_tag.text.startswith("window._sharedData ="):
                shared_data = re.sub("^window\._sharedData = ", "", script_tag.text)
                shared_data = re.sub(";$", "", shared_data)
                shared_data = json.loads(shared_data)
                return shared_data

    def extract_recent_instagram_post(node):
            return InstagramPost(
                post_id=node['id'],
                code=node['shortcode'],
                user=InstagramUser(user_id=node['owner']['id']),
                caption=HashTagSearch.extract_caption(node),
                display_src=node['display_url'],
                is_video=node['is_video'],
                created_at=node['taken_at_timestamp']
            )

    def extract_recent_query_instagram_post(node):
        return InstagramPost(
            post_id=node['id'],
            code=node['shortcode'],
            user=InstagramUser(user_id=node['owner']['id']),
            caption=HashTagSearch.extract_caption(node),
            display_src=node['display_url'],
            is_video=node['is_video'],
            created_at=node['taken_at_timestamp']
        )

    def extract_caption(node):
        if len(node['edge_media_to_caption']['edges']) > 0:
            return node['edge_media_to_caption']['edges'][0]['node']['text']
        else:
            return None

    def extract_owner_details(owner):
        username = None
        if "username" in owner:
            username = owner["username"]
        is_private = False
        if "is_private" in owner:
            is_private = is_private
        user = InstagramUser(owner['id'], username=username, is_private=is_private)
        return user

    def get_query_id(self, doc):
        query_ids = []
        for script in doc.find_all("script"):
            if script.has_attr("src"):
                text = requests.get("%s%s" % (self.instagram_root, script['src'])).text
                if "queryId" in text:
                    for query_id in re.findall("(?<=queryId:\")[0-9A-Za-z]+", text):
                        query_ids.append(query_id)
        print(query_ids)
        return query_ids


class HashTagSearchExample(HashTagSearch):
    def __init__(self):
        super().__init__()
        self.total_posts = 0

    def save_results(self, instagram_results):
        super().save_results(instagram_results)
        for i, post in enumerate(instagram_results):
            self.total_posts += 1
            print("%i - %s" % (self.total_posts, post.processed_text()))

def Yelp_info(yelp_id, yelp_key):
    yelp_api = YelpAPI(yelp_id, yelp_key)
    search_results = yelp_api.search_query(term='Neptune Oyster', location='Boston, MA')
    for business in search_results['businesses']:
        print (business['name'])

# if __name__ == '__main__':
#     log.basicConfig(level=log.INFO)
#     HashTagSearchExample().extract_recent_tag('food')
