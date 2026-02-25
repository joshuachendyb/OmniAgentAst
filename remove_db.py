import os
db_path = r'C:\Users\40968\.omniagent\chat_history.db'
if os.path.exists(db_path):
    os.remove(db_path)
    print('Database removed')
else:
    print('Database does not exist')