import json
import time
import asyncio
import httpx

# --- Settings ---
API_URL = "https://star-jwt-api1.lovable.app/api/public/token"
MAX_RETRIES = 4
RETRY_DELAY = 30

# --- Token Generation Logic ---

async def generate_single_token(client, uid: str, password: str):
    """API से एक टोकन जेनरेट करता है।"""
    try:
        url = f"{API_URL}?uid={uid}&password={password}"
        resp = await client.get(url, timeout=180)

        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception as e:
        print(f"UID {uid} के लिए त्रुटि: {e}")
        return None

async def process_account_with_retry(client, account, index):
    """एक अकाउंट को दोबारा कोशिश करने वाले लॉजिक के साथ प्रोसेस करता है।"""
    uid = account['uid']
    password = account['password']

    for attempt in range(MAX_RETRIES):
        token_data = await generate_single_token(client, uid, password)

        if token_data and "token" in token_data:
            return {
                "status": "success",
                "account": account,
                "token_data": token_data,
                "index": index
            }

        if attempt < MAX_RETRIES - 1:
            print(f"UID #{index + 1} {uid} - फ़ेल हुआ। {RETRY_DELAY} सेकंड बाद फिर से कोशिश की जाएगी...")
            await asyncio.sleep(RETRY_DELAY)

    return {
        "status": "failed",
        "account": account,
        "index": index
    }

async def main():
    """मुख्य फ़ंक्शन जो पूरी प्रक्रिया को चलाता है।"""
    input_file = "accounts.json"
    try:
        with open(input_file) as f:
            accounts = json.load(f)
    except FileNotFoundError:
        print(f"त्रुटि: '{input_file}' फ़ाइल नहीं मिली।")
        return
    except json.JSONDecodeError:
        print(f"त्रुटि: '{input_file}' एक मान्य JSON नहीं है या खाली है।")
        return

    print(f"🚀 {len(accounts)} अकाउंट्स के लिए टोकन बनाना शुरू किया जा रहा है...")
    start_time = time.time()

    # सभी रीजन के लिए अलग-अलग लिस्ट बनाएं
    result = {
        'IND': [], 'SG': [], 'ID': [], 'BR': [], 'VN': [], 
        'US': [], 'SAC': [], 'NA': [], 'RU': [], 'TH': [], 
        'TW': [], 'BD': [], 'PK': [], 'ME': [], 'CIS': [], 'EU': []
    }
    failed_accounts = []

    async with httpx.AsyncClient() as client:
        tasks = [process_account_with_retry(client, acc, i) for i, acc in enumerate(accounts)]
        responses = await asyncio.gather(*tasks)

        for res in responses:
            if res['status'] == 'success':
                account = res['account']
                token_data = res['token_data']

                # रीजन कोड के आधार पर सीधे region निर्धारित करें
                region_code = token_data.get('region', '').upper()

                # सभी संभावित रीजन कोड को मैप करें
                if region_code == 'IND':
                    region = 'IND'
                elif region_code == 'SG':
                    region = 'SG'
                elif region_code == 'ID':
                    region = 'ID'
                elif region_code == 'BR':
                    region = 'BR'
                elif region_code == 'VN':
                    region = 'VN'
                elif region_code == 'US':
                    region = 'US'
                elif region_code == 'SAC':
                    region = 'SAC'
                elif region_code == 'NA':
                    region = 'NA'
                elif region_code == 'RU':
                    region = 'RU'
                elif region_code == 'TH':
                    region = 'TH'
                elif region_code == 'TW':
                    region = 'TW'
                elif region_code == 'BD':
                    region = 'BD'
                elif region_code == 'PK':
                    region = 'PK'
                elif region_code == 'ME':
                    region = 'ME'
                elif region_code == 'CIS':
                    region = 'CIS'
                elif region_code == 'EU':
                    region = 'EU'
                else:
                    # अगर कोई अन्य region code आता है तो उसे BD में डालें
                    region = 'BD'

                result[region].append({
                    'uid': account['uid'],
                    'token': token_data['token']
                })
                print(f"✅ UID #{res['index'] + 1} {account['uid']} - टोकन जेनरेट हुआ ({region})")
            else:
                failed_accounts.append(res['account']['uid'])
                print(f"❌ UID #{res['index'] + 1} {res['account']['uid']} - टोकन जेनरेट नहीं हो सका।")

    # परिणामी टोकन को फ़ाइलों में सेव करें (सिर्फ उन रीजन के लिए जिनमें डेटा है)
    for region, tokens in result.items():
        if tokens:
            filename = f'tokens_{region.lower()}.json'
            with open(filename, 'w') as f:
                json.dump(tokens, f, indent=2)
            print(f"💾 {len(tokens)} टोकन {filename} में सेव किए गए।")

    # --- विस्तृत सारांश प्रिंट करें ---
    total_time = time.time() - start_time
    print("\n" + "="*40)
    print("✨ प्रोसेस पूरा हुआ! ✨")
    print(f"⏱️ कुल समय: {total_time:.2f} सेकंड")
    print(f"📊 कुल अकाउंट्स: {len(accounts)}")
    print(f"✔️ सफल टोकन: {len(accounts) - len(failed_accounts)}")
    print(f"❌ फ़ेल हुए अकाउंट्स: {len(failed_accounts)}")
    if failed_accounts:
        print(f"   -> फ़ेल हुए UIDs: {', '.join(failed_accounts)}")
    
    # रीजन-वाइज आंकड़े दिखाएं
    print("\n📌 रीजन-वाइज टोकन गणना:")
    for region, tokens in result.items():
        if tokens:
            print(f"   {region}: {len(tokens)} टोकन")
    print("="*40)

if __name__ == "__main__":
    asyncio.run(main())