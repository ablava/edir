"""
This config file contains constants describing 
the specific environment where this script is used.
IMPORTANT: refer to the code on how they are used.
"""

# LDAP server address to connect to, e.g. ldaps://server.domain.edu:636/
LDAPSERVER = ''
# User to bind with, e.g. cn=admin,o=DA
USER = ''
# Credentials for the above user in base64, e.g. bmljZSB0cnkK
PASSWORD = ''
# BaseDN of the directory, e.g. o=DA
BASEDN = ''
# Email domain name for users, e.g. @domain.edu
MAILDOMAIN = ''
# Pattern that identifies student user namess, e.g. _
STUPATTERN = ''
# Pattern that identifies guest users, e.g. starts with gst
GSTPATTERN = ''
# Pattern that identifies special Aruba attributes, e.g. Aruba-User-Role
ARUBAPATTERN = ''
# Server for the student home directories, e.g. stufileserver
STUSERVER = ''
# Server for the employee home directories, e.g. empfileserver
EMPSERVER = ''
# eDir share name for home directories, e.g. _PERSONAL,ou=Servers,o=DA
SHAREOU = ''
# OU where students are created, e.g. ,ou=Students,o=DA
STUDENTOU = ''
# OU where guests are created, e.g. ,ou=Visitors,o=DA
GUESTOU = ''
# OU where employees are created, e.g. ,ou=Visitors,o=DA
EMPOU = ''
# OU (and group name extension) that holds departmental groups, 
# e.g. _DEPARTMENT,ou=Departments,o=DA
DEPGROUPOU = ''
# OU that holds general user groups to support Mac logins, 
# e.g. ,ou=Resources,o=DA
GeneralMacUsersOU = ''
# General Mac user groups by type, e.g. Stu_GeneralMac_Users
StuGeneralMacUsers = ''
GuestGeneralMacUsers = ''
EmpGeneralMacUsers = ''
# General employee user group for shared folders, e.g. Emp_GeneralWS_Users
EmpGeneralWSUsers = ''
# Email address to send auto-notifications from, e.g. user@server.domain.edu
FROM = ''
# Email address to send the notifications to, e.g. user@domain.edu
TO = ''
# Email server address, e.g. mail.domain.edu
MAILSERVER = ''
