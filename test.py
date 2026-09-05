
import akasha
import dotenv

dotenv.load_dotenv()

print('starting test.py')

# # 判斷是否有環境變數 GEMINI_API_KEY
# if 'GEMINI_API_KEY' not in dotenv.os.environ:
#     raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it in the .env file.")

qa = akasha.ask(model='gemini:gemini-3.6-flash', verbose=True)
response = qa('hello world')
print(response)