import requests
import json
import datetime
import xml.etree.ElementTree as ET
import config as cfg

log_file = f"LOG-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"

test_taw_u = cfg.test_taw_username
test_taw_p = cfg.test_taw_password

taw_u = cfg.taw_username
taw_p = cfg.taw_password
taw_url = cfg.taw_url

taw_headers = {
	'Content-Type' : 'application/x-www-form-urlencoded',
}

ord_headers = {
	'Authorization' : cfg.ord_auth,
	'Content-Type' : 'application/json'
}

ord_url = cfg.ord_url

ord_tag_id_await_tracking = '30068'
ord_tag_name_await_tracking = 'Awaiting Tracking'

ord_get_dropship_orders_params = {
	'tag' : ord_tag_name_await_tracking
}
	
def log(str):
	print(str, flush=True)
	with open(log_file, 'a') as file:
		file.write(f"{str}\n\r")

#### GET ALL AWAITING TRACKING ORDERS FROM ORDORO ###
log("Requesting all orders with 'Awaiting Tracking' from ordoro...")

r = requests.get(f"{ord_url}/order", params=ord_get_dropship_orders_params, headers=ord_headers)
robj = json.loads(r.content)

ord_orders = robj['order']

log(f"Found {len(ord_orders)} to process.")

for eachOrder in ord_orders:
	PONumber = eachOrder['order_number']
	taw_order_id = ''
	
	log(f"\n\r---- {PONumber} ----")
	
	# LOOP THROUGH ORDER COMMENTS TO FIND THE ORDER NUMBER RETURNED BY TAW
	for eachComment in eachOrder['comments']:
		if("TAW_ORD_ID" in eachComment['text']):
			taw_order_id = eachComment['text'].split(':')[1]
			
	log(f"[{PONumber}] TAW order id {taw_order_id}")
	log(f"[{PONumber}] Requesting tracking info from TAW...")
			
	# ASK FOR TRACKING INFO FROM TAW
	r = requests.post(f"{taw_url}/GetTrackingInfo", data=f"UserID={taw_u}&Password={taw_p}&OrderNumber={taw_order_id}&PONumber={PONumber}", headers=taw_headers)
	
	log(f"[{PONumber}] Response from TAW:\n\r{r.content.decode('UTF-8')}")

	try:
		# PARSE TRACKING INFO FROM TAW RESPONSE
		root = ET.ElementTree(ET.fromstring(r.content)).getroot()
		record = root.find('Record')
		
		log(f"[{PONumber}] Tracking info found! Parsing...")
		
		data = {}
		
		order_date_str = record.find('OrderDate').text
		order_date_obj = datetime.datetime.strptime(order_date_str, '%m/%d/%Y')
		order_date_str = order_date_obj.strftime('%Y-%m-%dT%H:%M:%S.000Z')
		
		data['ship_date'] = order_date_str
		
		log(f"[{PONumber}] Ship date: {data['ship_date']}")
		
		data['tracking_number'] = record.find('TrackNum').text.strip()
				
		log(f"[{PONumber}] Tracking number: {data['tracking_number']}")
		
		# IF NO TRACKING NUMBER, LOG IT AND GO ON TO THE NEXT ONE
		if (data['tracking_number'] == ""):
			log(f"[{PONumber}] No tracking number found. Skipping.")
			continue
		
		data['carrier_name'] = record.find('Type').text.strip()
		
		# IF NO VENDOR, LOG IT AND GO ON TO THE NEXT ONE
		if (data['carrier_name'] == ""):
			log(f"[{PONumber}] No vendor found. Skipping.")
			continue
			
		data['shipping_method'] = "ground"
		data['cost'] = 14
		
		log(f"[{PONumber}] Vendor: {data['carrier_name']}")
		log(f"[{PONumber}] Sending to ordoro...")
		
		# SEND TRACKING INFO TO ORDORO
		r = requests.post(f"{ord_url}/order/{PONumber}/shipping_info", data=json.dumps(data), headers=ord_headers)
		
		log(f"[{PONumber}] Response from ordoro:\n\r{r.content.decode('UTF-8')}")
		log(f"[{PONumber}] Removing 'Awaiting Tracking' tag...")
		
		# DELETE AWAITING TRACKING TAG FROM ORDER
		r = requests.delete(f"{ord_url}/order/{PONumber}/tag/{ord_tag_id_await_tracking}", headers=ord_headers)
		
		log(f"[{PONumber}] Response from ordoro:\n\r{r.content.decode('UTF-8')}")

	except Exception as err:
		log(f"[{PONumber}] Error parsing tracking info...\n\rException:\n\r{err}\n\rLast Response:\n\r{r.content.decode('UTF-8')}")

	log(f"[{PONumber}] Finished.")
