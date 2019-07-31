import requests
import json
import datetime
import xml.etree.ElementTree as ET

log_file = f"LOG-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"

taw_u = '***REMOVED***'
taw_p = '***REMOVED***'
taw_url = '***REMOVED***'

taw_headers = {
	'Content-Type' : 'application/x-www-form-urlencoded',
}

ord_headers = {
	'Authorization' : '***REMOVED***',
	'Content-Type' : 'application/json'
}

ord_url = '***REMOVED***'

ord_tag_id_await_tracking = '30068'
ord_tag_name_await_tracking = 'Awaiting Tracking'

### GET ALL AWAITING TRACKING ORDERS FROM ORDORO ###
ord_get_dropship_orders_params = {
	'tag' : ord_tag_name_await_tracking
}

def iprint(str):
	print(str, flush=True)
	
def log(str):
	iprint(str)
	with open(log_file, 'a') as file:
		file.write(f"{str}\n\r")

log("Requesting all orders with 'Awaiting Tracking' from ordoro...")

r = requests.get(f"{ord_url}/order/", params=ord_get_dropship_orders_params, headers=ord_headers)
robj = json.loads(r.content)

ord_orders = robj['order']

log(f"Found {len(ord_orders)} to process.")

for eachOrder in ord_orders:
	PONumber = eachOrder['order_id']
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
		data['ship_date'] = record.find('ShipDate').text
		
		log(f"[{PONumber}] Ship date: {data['ship_date']}")
		
		data['tracking'] = {}
		data['tracking']['tracking'] = record.find('TrackNum').text.strip()
				
		log(f"[{PONumber}] Tracking number: {data['tracking']['tracking']}")
		
		# IF NO TRACKING NUMBER, LOG IT AND GO ON TO THE NEXT ONE
		if (data['tracking']['tracking'] == ""):
			log(f"[{PONumber}] No tracking number found. Skipping.")
			continue
		
		data['tracking']['vendor'] = record.find('Type').text.strip()
		
		# IF NO VENDOR, LOG IT AND GO ON TO THE NEXT ONE
		if (data['tracking']['vendor'] == ""):
			log(f"[{PONumber}] No vendor found. Skipping.")
			continue
		
		log(f"[{PONumber}] Vendor: {data['tracking']['vendor']}")
		log(f"[{PONumber}] Sending to ordoro...")
		
		# SEND TRACKING INFO TO ORDORO
		shipment_id = eachOrder['shipments'][0]['shipment_id']
		r = requests.post(f"{ord_url}/shipment/{shipment_id}/tracking/", data=json.dumps(data), headers=ord_headers)
		
		log(f"[{PONumber}] Response from ordoro:\n\r{r.content.decode('UTF-8')}")
		log(f"[{PONumber}] Removing 'Awaiting Tracking' tag...")
		
		# DELETE AWAITING TRACKING TAG FROM ORDER
		r = requests.delete(f"{ord_url}/order/{PONumber}/tag/{ord_tag_id_await_tracking}/", headers=ord_headers)
		
		log(f"[{PONumber}] Response from ordoro:\n\r{r.content.decode('UTF-8')}")

	except Exception as err:
		log(f"[{PONumber}] Error parsing tracking info...\n\rException:\n\r{err}\n\rLast Response:\n\r{r.content.decode('UTF-8')}")

	log(f"[{PONumber}] Finished.")
