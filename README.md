This is the Concurrent systems project

It handles up to 4 users at a time any more than 4 will go to a waiting queue

Users can look at the document on the dashboard, only one can edit at a time

To run this tool:

-python
-flask (pip install)
-have run init_db.py (sets up the database)

Note:
for testing this tool, as the focus on this tool is on concurrency it doesnt concern it's self with cookies managment
so for testing multiple users from the same device use different browsers & their incognito conterpart
Personally found that multiple chrome incognito tabs share cookies so to test the system like it would be expected with users from different devices use different browsers