#!/usr/bin/python
#
# cnb.py - (c) 2007 Matthew J Ernisse <mernisse@ub3rgeek.net>
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
# scrape the Canandaigua National Bank and Trust online banking for balance
# and insert into an RRD for graphing.
import logging
from rrdtool import *
import re
import sys
import os
import mechanize
from urllib2 import HTTPError

#
# Your username / password for the online banking website.  This script should
# be owner-readable ONLY because of the cleartext credentials.  The script 
# DOES NOT check, it is up to YOU.
#
USERNAME = ""
PASSWORD = ""

#
# If you simply change BASE to the path to this script, it will be used
# for all the files created / used by this script.  You can customize the 
# files individually if you like.
#
BASE="/staff/mernisse/bin/scrapers"
#
# Set your e-mail address here, this goes into the user-agent so your bank
# can e-mail you if they don't like you scraping them.
#
OWNER='mernisse@ub3rgeek.net'

#
# Canandaigua National Bank now uses Client SSL certificates to validate
# users.  Not supplying it will cause additional, random questions to be
# asked.  To make the certs, you need to export the certificate from your
# browser, as a PKCS12 file, then use openssl to convert the file into
# PEM format.
#
# EG:
# openssl pkcs12 -clcerts -nokeys -in ~/cnb.pkcs12.p12 -out cnb_cert.pem
# openssl pkcs12 -nocerts -in ~/cnb.pkcs12.p12 -out cnb_key.pem
# openssl rsa -passin pass:<pass> -in cnb_key.pem -out cnb_key-d.pem
#
KEY=BASE + '/cnb_key-d.pem' 
CERT=BASE + '/cnb_cert.pem'

#
# You can setup your proxys here, if you do so, please uncomment the
# proxy block below.
#
proxy = { 
	"https": None,
	"http": None,
	 }

#
# You can change these if you like, though you shouldn't need to.
#
RRD=BASE + "/cnb-balance.rrd"
COOKIE=BASE + "/cnbcookie.txt"

# End User Configuration
host = "cnbsec1.cnbank.com"

start_page = "https://cnbsec1.cnbank.com/CAN_40/Common/SignOn/Start.asp"
landing_page = "https://cnbsec1.cnbank.com/CAN_40/Common/Accounts/Accounts.asp"


if not USERNAME or not PASSWORD:
	print "Please edit this file and follow the directions in the comments"
	print "\n"
	sys.exit(0)

br = mechanize.Browser()
cj = mechanize.LWPCookieJar()

try:
	cj.revert(COOKIE)
except:
	pass

br.add_client_certificate(
	host, 
	KEY,
	CERT
	) 

br.addheaders = [ 
	("User-agent", "Mozilla/5.0 (X11; U; i386; " + OWNER + ")"),
	]
#
#if proxy:
#	br.set_proxies(proxy)
#
br.set_cookiejar(cj)
br.set_handle_robots(False)
br.set_handle_refresh(True, 10, True)
br.set_handle_redirect(True)

#
# Debug
#
#br.set_debug_http(True)
#br.set_debug_responses(True)
#br.set_debug_redirects(True)
#logger = logging.getLogger("mechanize")
#logger.addHandler(logging.StreamHandler(sys.stdout))
#logger.setLevel(logging.DEBUG)

try:
	br.open(start_page)
except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))

cj.save(COOKIE)
assert br.viewing_html()
br.select_form('form1')
br["SignOnID"] = USERNAME 
br["Password"] = PASSWORD

try:
	r = br.submit()
	cj.save(COOKIE)
except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))

try:
	r = br.open(landing_page)
except HTTPError, e:
	sys.exit("%d: %s" % (e.code, e.msg))

page = r.get_data()

accounts = []

for balance in re.findall("\$([\d,]+[\d\.]+[\d]{2})", page):
	accounts.append(balance.replace(",",""))

# balance is now  a list of balances	
# The first one is the checking account available balance.

cnb_rrd = RoundRobinDatabase(RRD)

if not os.path.exists(RRD):
	# 1 row per 4 h = 6 rows / day = 2190 rows / year = 6570 / 3y
	cnb_rrd.create(
		DataSource("checking", type=GaugeDST, heartbeat=14400, min='0', max='100000000'),
		RoundRobinArchive(cf=LastCF, xff=0, steps=1, rows=6570),
		step=7200)

cnb_rrd.update(Val(accounts[0]), t=['checking'])
