import smtplib
from datetime import date
from email.message import EmailMessage

# Hard code values for gmail account (also need to setup app-specific passwords)
# no 2fa: https://myaccount.google.com/lesssecureapps
# 2fa (recommended): https://myaccount.google.com/apppasswords
email_address = ""
email_password = ""

# Build email message from updates.txt
in_file = open("updates.txt", "r")
msg_body = ""

print("Building email...", end="")
fileLines = in_file.readlines()
for i in range(len(fileLines)):
	if "\x09\x09\x09" in fileLines[i]:
		fileLines[i] = fileLines[i].replace("\x09\x09\x09", "\x09")
	msg_body += fileLines[i]
print("Done")
# Build email and send to recipient
print("Sending email...", end="")
msg = EmailMessage()
msg['Subject'] = 'IPO updates for: ' + str(date.today())
msg['From'] = email_address
msg['To'] = email_address # Hard code once we know the value (alternative is we send to a array of emails)
msg.set_content(msg_body)

with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
	smtp.login(email_address, email_password)
	smtp.send_message(msg)	
print("Done")
