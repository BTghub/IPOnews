import smtplib
import mysql.connector
from datetime import date, datetime
from email.message import EmailMessage
from requests_html import HTMLSession

# Initialization

# Hard code values for gmail account (also need to setup app-specific passwords)
# no 2fa: https://myaccount.google.com/lesssecureapps
# 2fa (recommended): https://myaccount.google.com/apppasswords
email_address = ""
email_password = ""

update_msg = "" # Will hold the email as it's built to be passed to send_email

# Endpoints with listing data
nasdaqUP = "https://www.nasdaq.com/markets/ipos/activity.aspx?tab=upcoming"
nasdaqRP = "https://www.nasdaq.com/markets/ipos/activity.aspx?tab=pricings"
TSVrecent = "https://www.tsx.com/json/company-directory/recent/tsxv"
TSXrecent = "https://www.tsx.com/json/company-directory/recent/tsx"

# Database connection
connection = mysql.connector.connect(host='localhost', database='iponews', user='root', password='', use_pure=True)
if not connection.is_connected():
    print("MySQL: service cannot be found")
    exit(-1)

# Helper Functions

"""
export_row_data(rowHTML)

Description:
    Converts the row data to an array for easier handling
Input:
    rowHTML         Raw HTML source of a row
"""
def export_row_data(rowHTML):
    out_array = []
    rowCont = rowHTML.find('td')
    keep = 0
    for td in rowCont:
        if not (keep == 4 or keep == 5):
            out_array.append(td.text)
        keep += 1
    return out_array

"""
return_between(in_string, start_tag, end_tag, INCL)

Description:
    Returns a substring of in_string delineated by start_tag and end_tag
Input:
    in_string       Input string to parse
    start_tag       Defines beginning of substring
    end_tag         Defines end of substring
    INCL            Boolean to keep or discard tags
"""
def return_between(in_string, start_tag, end_tag, INCL):
  start_idx = in_string.index(start_tag) 
  end_idx = in_string.index(end_tag)
  if INCL:
    out_string = in_string[start_idx:end_idx+len(end_tag)]
  else:
    out_string = in_string[start_idx+len(start_tag):end_idx]

  return out_string

"""
parse_array(in_string, start_tag, end_tag)

Description:
    Returns an array of strings that exists repeatedly in in_string
Input:
    in_string       Input string to parse
    start_tag       Defines beginning of substring
    end_tag         Defines end of substring
"""
def parse_array(in_string, start_tag, end_tag):
  out_array = []
  start_idx = in_string.find(start_tag)
  while start_idx >= 0:
    end_idx = in_string.find(end_tag)
    if end_idx < 0:
      break
    out_array.append(in_string[start_idx+len(start_tag):end_idx])
    in_string = in_string[end_idx+len(end_tag):]
    start_idx = in_string.find(start_tag)

  return out_array

"""
execute_sql(sql_query)

Decsription:
    Returns the results of the query sql_query
Input:
    sql_query       String of query to be executed
"""
def execute_sql(sql_query):
    global connection
    DB = connection.cursor()
    results = None
    DB.execute(sql_query)
    results = DB.fetchall()
    DB.close()

    return results

"""
insertNDdata(db_table, NDdata)
insertTSdata(db_table, TSdata)

Description:
    Inserts *data into db_table and commits changes to the database
Input:
    db_table        Table name of destination for data
    *data           Array of data to be inserted into database 
"""
def insertNDdata(db_table, NDdata):
    global connection
    DB = connection.cursor(prepared=True)
    insertQuery = "insert into " + db_table + " (cname , symbol , market , price , adate) values (%s, %s, %s, %s, %s)"
    data = tuple(NDdata)
    DB.execute(insertQuery, data)
    connection.commit() # Makes changes to DB peristent
    DB.close()

def insertTSdata(db_table, TSdata):
    global connection
    DB = connection.cursor(prepared=True)
    insertQuery = "insert into " + db_table + " (cname , symbol, adate) values (%s, %s, %s)"
    data = tuple(TSdata)
    DB.execute(insertQuery, data)
    connection.commit() # Makes changes to DB peristent
    DB.close()

# Main Functionality

"""
send_updates(userEmail, userPass)

Description:
    Creates and sends the email to the desired recipient
Input:
    userEmail       Email account of the sender
    userPass        Associated app password to access the account
"""
def send_updates(userEmail, userPass, recipient, new_msg):
    # Build email and send to recipient
    msg = EmailMessage()
    msg['Subject'] = 'IPO updates for: ' + str(date.today())
    msg['From'] = email_address
    msg['To'] = recipient
    msg.set_content(new_msg)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(userEmail, userPass)
        smtp.send_message(msg)	

"""
getWebpage(url)

Description:
    Download page source from url
Input:
    url             Destination webpage
"""
def getWebpage(url):
    resp = None
    with HTMLSession() as html:
        resp = html.get(url).html # Submits Get request to URL and stores html
    
    return resp

"""
parseNasdaq(UPhtml)

Description:
    Parse the content on the NASDAQ IPO pages
Input:
    NDhtml          Html source of NASDAQ website
"""
def parseNasdaq(NDhtml):
    tableData = NDhtml.find('table')[0] # Only first table contains data we want
    rowData = tableData.find('tr')[1:] # First row is the column titles so we don't need those
    out_array = []
    for row in rowData:
        out_array.append(export_row_data(row))

    return out_array

"""
parseTsxv(TSXVhtml)

Description:
    Parse the content on the TSXV pages
Input:
    TSXVhtml        Html source of TSXV website
"""
def parseTsxv(TSXVhtml):
    pageData = return_between(TSXVhtml.text, "[", "]", False)
    rowData = parse_array(pageData, "{", "}")
    out_array = []
    for row in rowData:
        row_array = []
        row_array.append(return_between(row, "\"name\":", ",", False).strip("\""))
        date = return_between(row[row.index(",")+1:], "\"date\":", ",", False)
        date = datetime.fromtimestamp(int(date)).strftime('%Y-%m-%d')
        row_array.append(date)
        row_array.append(row[row.rindex(":")+1:].strip("\""))
        out_array.append(row_array)
    return out_array

"""
NotinDB(db_table, cname)

Description:
    Runs a select query on database to see if entry already exist
Input:
    db_table        Name of table to query
    cname           Company name (key) to use in query
"""
def NotinDB(db_table, cname):
    newQuery = "select * from " + db_table + " where cname=\"" + cname + "\";" 
    found = execute_sql(newQuery)
    if len(found) == 0:
        return True
    return False

"""
CheckForUpdates(parsedData, db_table)

Description:
    Compares the parsed data with the database and adds new entries to update_msg
Input:
    parsedData      Data returned by the parsing functions above
    db_table        Name of table with associated data
"""
def CheckForUpdates(parsedData, db_table):
    global update_msg
    for row in parsedData:
        if NotinDB(db_table, row[0]):
            if "nasdaq" in db_table:
                insertNDdata(db_table, row)
                new_entry = "{4}    {0}    {1}    {2}    {3}\n".format(*row)
                update_msg += new_entry
            if "tsx" in db_table or "tsv" in db_table:
                insertTSdata(db_table, row)
                new_entry = "{1}    {0}    {2}\n".format(*row)
                update_msg += new_entry

# main functionality
up_array = parseNasdaq(getWebpage(nasdaqUP))
rp_array = parseNasdaq(getWebpage(nasdaqRP))
tsx_array = parseTsxv(getWebpage(TSXrecent))
tsv_array = parseTsxv(getWebpage(TSVrecent))

update_msg += "NASDAQ New Upcoming IPOs:\n\n"
CheckForUpdates(up_array,"nasdaq_upcoming")
update_msg += "\nNASDAQ New Recently Priced IPOs:\n\n"
CheckForUpdates(rp_array,"nasdaq_recent")
update_msg += "\nTSX New Recent IPOs:\n\n"
CheckForUpdates(tsx_array,"tsx_recent")
update_msg += "\nTSVQ New Recent IPOs:\n\n"
CheckForUpdates(tsv_array,"tsv_recent")

print(update_msg) # Will be used as message body for email

# Cleanup
connection.close()

    
