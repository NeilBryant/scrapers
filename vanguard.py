#!/usr/bin/python
#
# vanguard.py - (c) 2012 Matthew J Ernisse <mernisse@ub3rgeek.net>
#
# Redistribution and use in source and binary forms, 
# with or without modification, are permitted provided 
# that the following conditions are met:
#
#    * Redistributions of source code must retain the 
#      above copyright notice, this list of conditions 
#      and the following disclaimer.
#    * Redistributions in binary form must reproduce 
#      the above copyright notice, this list of conditions 
#      and the following disclaimer in the documentation 
#      and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT 
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS 
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE 
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, 
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, 
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS 
# OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND 
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR 
# TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE 
# USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import logging
import re
import sys
import os
import mechanize

import BeautifulSoup
from urllib2 import HTTPError

#
# Your username / password for the online banking website.  This script should
# be owner-readable ONLY because of the cleartext credentials.  The script 
# DOES NOT check, it is up to YOU.
#
USERNAME = ''
PASSWORD = ''
QUESTIONS = {
#	"Place the Security Question Here": "And the Answer Here.",
}

#
# If you simply change BASE to the path to this script, it will be used
# for all the files created / used by this script.  You can customize the 
# files individually if you like.  Default is to put them in the same
# directory as the script.
#
BASE=os.path.dirname(sys.argv[0])

#
# Set VANGUARD_TAB if you want to write a tab file down.
# This prevents the RRD from being updated.
#
VANGUARD_TAB=None

#
# Set your e-mail address here, this goes into the user-agent so your bank
# can e-mail you if they don't like you scraping them.
#
OWNER=''

DEBUG=None
#DEBUG=True

#
# You can setup your proxys here, if you do so, please uncomment the
# proxy block below.
#
proxy = { 
	"https": "",
	"http": "",
	 }

#
# You can change these if you like, though you shouldn't need to.
#
RRD=BASE + "/vanguard-balance.rrd"

# End User Configuration


def sanitize(str):
	if not str:
		return ''

	return str.strip().replace('$', '').replace(',', '')

def tabify(str):
	if not str:
		return ''

	return str.lower().replace(" ", "_")[:8]


start_page = 'https://personal.vanguard.com/us/home'
balance_page = 'https://personalp.vanguard.com/us/TPView'


if not USERNAME or not PASSWORD or not OWNER or not QUESTIONS:
	print "Please edit this file and follow the directions in the comments"
	print "\n"
	sys.exit(0)

br = mechanize.Browser()

br.addheaders = [ 
	("User-agent", "Mozilla/5.0 (X11; U; Linux i686; en-US; rv 1.0) %s" %
	               (OWNER)),
	]

#
#if proxy:
#	br.set_proxies(proxy)
#

br.set_handle_robots(False)
br.set_handle_refresh(True, 10, True)
br.set_handle_redirect(True)

#
# Debug
#
if DEBUG == True:
	br.set_debug_http(True)
	br.set_debug_responses(True)
	br.set_debug_redirects(True)
	logger = logging.getLogger("mechanize")
	logger.addHandler(logging.StreamHandler(sys.stdout))
	logger.setLevel(logging.DEBUG)

try:
	if DEBUG:
		print "Trying to open %s" % (start_page)

	br.open(start_page)
except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))

assert br.viewing_html()


#
# username form
#
br.select_form('LoginForm')
br['USER'] = USERNAME

try:
	if DEBUG:
		print "Trying to submit username form"

	r = br.submit()
#	cj.save(COOKIE)
except HTTPError, e:
	print "%d: %s" % (e.code, e.msg)
	sys.exit(1)

try:
	soup = BeautifulSoup.BeautifulSoup(r.get_data())
except Exception, e:
	print "Caught Exception %s" % ( str(e) )
	print r.get_data()
	sys.exit(1)


#
# security question form
#
question = soup.findAll('table', attrs={'class': 'summaryTable pad'})[0]
question = question.findAll('td')[3].string
question = question.strip().lower()


if not question in QUESTIONS.keys():
	print 'Question %s not found in config' % question
	sys.exit(1)

br.select_form('LoginForm')
br['ANSWER'] = QUESTIONS[question]

try:
	if DEBUG:
		print "Trying to submit security question form"

	r = br.submit()
except HTTPError, e:
	print "%d: %s" % (e.code, e.msg)
	sys.exit(1)

#
# password form
#
br.select_form('LoginForm')
br['PASSWORD'] = PASSWORD

try:
	if DEBUG:
		print "Trying to submit password form"

	r = br.submit()
except HTTPError, e:
	print "%d: %s" % (e.code, e.msg)
	sys.exit(1)


#
# get portfolio total
#

r = br.open(balance_page)

try:
	soup = BeautifulSoup.BeautifulSoup(r.get_data())
except Exception, e:
	print "Caught Exception %s" % ( str(e) )
	print r.get_data()
	sys.exit(1)

portfolio = soup.findAll('td', attrs={'class': 
	'nowrap nr right noBotBorder padRight padLeft noPadBottom'})[0].string

total = sanitize(portfolio)

if not total:
	sys.exit(1)

# The output format of the tab should be compatible with the
# trp scraper by jwm@horde.net
if VANGUARD_TAB:
	fd = open(VANGUARD_TAB, "w")

	fd.write("vang %s\n" % ( total ))
	fd.close()
	sys.exit(0)

from rrd import *
rrd = RoundRobinDatabase(RRD)

if not os.path.exists(RRD):
	# 1 row per 4 h = 6 rows / day = 2190 rows / year = 6570 / 3y
	rrd.create(
		DataSource("balance", type=GaugeDST, heartbeat=14400, min='0', max='100000000'),
		RoundRobinArchive(cf=LastCF, xff=0, steps=1, rows=6570),
		step=7200)
try:
	rrd.update(Val(total), t=['balance'])
except Exception, e:
	print "Cannot update RRD, %s" % (str(e))

