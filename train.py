#!/usr/bin/python3
import argparse
import requests
import datetime
from bs4 import BeautifulSoup
import re
import json
import time
from datetime import datetime,timedelta

service_url = "https://www.realtimetrains.co.uk"

parser = argparse.ArgumentParser(description="RTT JSON Parser",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("-s", "--station", default="MAN", help="Set the station to fetch (Default is \"MAN\" for Manchester Picadilly)")
args = vars(parser.parse_args())
station_name = args["station"]

search_time = datetime.today() #Assume search is for now


def formatTime(timeStr):

    match len(timeStr):
        case 4:
            return timeStr[:2] + ":" + timeStr[2:4] + ":" + "00"
        case 0:
            return "";
        case _:
            return timeStr[:2] + ":" + timeStr[2:4] + ":" + timeStr[4:]   
    
def getUnixTime(time_str):

    if not ((time_str is None) or (time_str == "")):
        # parse the input time string into a struct_time object
        input_time_struct = time.strptime(str(time_str), "%H:%M:%S")

        # create a datetime object for the input time at search_time
        datetime_at_input_time = datetime.combine(search_time, datetime.min.time()) + timedelta(hours=input_time_struct.tm_hour, minutes=input_time_struct.tm_min)

        search_time_hours = search_time.strftime("%H")
        # if the resulting datetime object is in the past, add one day to get tomorrow's date
        if (0 <= int(search_time_hours) <= 5):
            if int(time_str[:2]) >= 19 and datetime_at_input_time > search_time:
                datetime_at_input_time -= timedelta(days=1) 
        else:
            if (21 <= int(search_time_hours) <= 23) and datetime_at_input_time.strftime("%H") < 3:
                datetime_at_input_time += timedelta(days=1)

        
        # convert the datetime object to Unix time
        unix_time = int(datetime_at_input_time.timestamp())
        #print("C: " + str(datetime_at_input_time))

        return unix_time
    else:
        return 0;

search_time_from = search_time - timedelta(hours=2)
search_time_to = search_time + timedelta(hours=4)

search_url = service_url + "/search/detailed/gb-nr:" + station_name + "/" + search_time_from.strftime("%Y-%m-%d") + "/" + search_time_from.strftime("%H%M") + "-" + search_time_to.strftime("%H%M") + "?stp=WVS&show=all&order=wtt"
#print(search_url)

response = requests.get(search_url)

soup = BeautifulSoup(response.text, 'html.parser')

services = soup.find_all('a', class_='service')

data = []

for service in services:

    station_fullname = soup.find('div', class_='header-text').find('h3').text.replace(" \n            Live Departures\n", "").replace("\n            ", "")
    #print("A: " + repr(station_fullname))
    station_fullname = re.sub(" from.*", "", str(station_fullname))
    station_fullname = re.sub(" around.*", "", str(station_fullname))
    station_fullname = station_fullname.replace("\n", "")
    #print("B: " + repr(station_fullname))
    url_service = service.get("href")
    response_service = requests.get(service_url + url_service)
    soup_service = BeautifulSoup(response_service.text, 'html.parser')


    identity_tags = soup_service.find_all('span', class_='identity')
    identities = []
    
    # Fix for issue where trains were displaying multiple times whenever a route includes a reverse
    for identity_tag in identity_tags:
        identity = identity_tag.text.strip() if identity_tag else none
        if not identity in identities:
            identities.append(identity)


    train_id=""
    train_uid=""


    service_info_panel = soup_service.find('div', class_='infopanel')
    if service_info_panel is not None:
        service_info = service_info_panel.find('li')
        if service_info is not None:
           pattern_uid = r"(?<=UID )\w*(?=,)"
           pattern_id = r"(?<=identity) [0-9A-Z]{4}"
           match_train_uid = re.search(pattern_uid, service_info.text)
           match_train_id = re.search(pattern_id, service_info.text)
           train_uid=match_train_uid.group(0).strip() if match_train_uid is not None else ""
           train_id=match_train_id.group(0).strip() if match_train_id is not None else ""

    plan_arr = service.select("div.plan.a")[0]
    act_arr = service.select("div.real.a")[0]
    plan_dep = service.select("div.plan.d")[0]
    act_dep = service.select("div.real.d")[0]

    if plan_arr is not None:
        plan_arr = plan_arr.text
    else:
        plan_arr = ""

    if act_arr is not None:
        act_arr = act_arr.text
    else:
        act_arr = ""

    if plan_dep is not None:
        plan_dep = plan_dep.text
    else:
        plan_dep = ""

    if act_dep is not None:
        act_dep = act_dep.text
    else:
        act_dep = ""

            
    is_cancelled = False
    if (act_dep == "Cancel") or (act_arr == "Cancel"):
        act_dep = ""
        act_arr = ""
        is_cancelled = True

    as_required = False
    if act_dep == "(Q)":
        act_dep = ""
        as_required = True

    is_delayed = False
    if (act_dep == "Delay") or (act_arr == "Delay"):
        act_dep = ""
        act_arr = ""
        is_delayed = True

    
    #print("A: " + str(plan_dep))
    plan_arr = formatTime(plan_arr.replace("\u00bc", "15").replace("\u00bd", "30").replace("\u00be", "45").replace("pass", ""))
    if "pass" in act_arr:
        act_arr = ""
    else: 
        act_arr = formatTime(act_arr.replace("\u00bc", "15").replace("\u00bd", "30").replace("\u00be", "45").replace("N/R", ""))
    if "pass" in plan_dep:
        plan_dep = ""
    else:
        plan_dep = formatTime(plan_dep.replace("\u00bc", "15").replace("\u00bd", "30").replace("\u00be", "45"))
    act_dep = formatTime(act_dep.replace("\u00bc", "15").replace("\u00bd", "30").replace("\u00be", "45").replace("N/R", ""))

    #print("B: " + str(plan_dep))
    plan_arr = getUnixTime(plan_arr) if (plan_arr != "::") else 0
    act_arr = getUnixTime(act_arr) if (act_arr != "::") else 0
    plan_dep = getUnixTime(plan_dep) if (plan_dep != "::") else 0
    #print("D: " + str(plan_dep))
    act_dep = getUnixTime(act_dep) if (act_dep != "::") else 0

    is_bus = False
    tid = service.find('div', class_="tid")
    if tid.find("span", class_="glyphicons glyphicons-bus"):
        is_bus = True

    # This doesn't work - columns don't always line up (number of divs varies)
    stop_tags = soup_service.find_all('div', class_='location')

    stops = []

    after_this_station = False

    if is_bus:
        for stop in stop_tags:
            stop_location=stop.find('div', class_='location')
            
            
            if stop_location is None:
                continue
            else:
                stop_location=stop.find('a')

            stop_location_fullname = re.sub("\[.*?\]", "", stop_location.text).strip()
            stop_location_short = stop_location.text.replace(stop_location_fullname, "").strip().replace("[","").replace("]","")
            
            gbtt_tag = stop.find('div', class_='gbtt')
            stop_plan_arr = ""
            stop_plan_arr_tmp = gbtt_tag.find('div', class_='arr')
            if stop_plan_arr_tmp is not None:
                stop_plan_arr = formatTime(stop_plan_arr_tmp.text.replace("\u00bc", "15").replace("\u00bd", "30").replace("\u00be", "45").replace("pass", ""))

            stop_plan_dep = ""
            stop_plan_dep_tmp = gbtt_tag.find('div', class_='dep')
            if stop_plan_dep_tmp is not None:
                stop_plan_dep = formatTime(stop_plan_dep_tmp.text.replace("\u00bc", "15").replace("\u00bd", "30").replace("\u00be", "45").replace("pass", ""))

            #if stop_location_short == station_name:
            #    after_this_station = True


            stop_plan_arr = getUnixTime(stop_plan_arr)
            stop_plan_dep = getUnixTime(stop_plan_dep)

            if stop_plan_dep == 0:
                if plan_dep == 0:
                    if stop_plan_arr > plan_arr:
                        after_this_station = True
                else:
                    if stop_plan_arr > plan_dep:
                        after_this_station = True
            else:
                if plan_dep == 0:
                    if stop_plan_dep > plan_arr:
                        after_this_station = True
                else:
                    if stop_plan_dep > plan_dep:
                        after_this_station = True


            stop_datum = {
                            "distance": 0.00,
                            "location":stop_location_fullname,
                            "location_short":stop_location_short,
                            "plan_arr":stop_plan_arr,
                            "plan_dep":stop_plan_dep,
                            "act_arr":0,
                            "act_dep":0,
                            "delay":0,
                            "platform":"",
                            "path":"",
                            "line":"",
                            "is_station":True,
                            "stops_here":True,
                            "after_this_station":after_this_station if not stop_location_short == station_name else False
                        }
            stops.append(stop_datum)
            
    else:
        for stop in stop_tags:
            stop_location=stop.find('div', class_='location')
            if stop_location is None:
                continue
            else:
                stop_location=stop.find('a')

    #        stop_location=stop_location.find('a').text if 'a' in stop_location else ""


            platform_tag = stop.find('div', class_='platform')
            if platform_tag is not None:
                stop_platform = platform_tag.text
            else:
                stop_platform = ""
            wtt_tag = stop.find('div', class_='wtt')
            realtime_tag = stop.find('div', class_='realtime')    
            
            stop_stops_here = True

            stop_plan_arr = ""
            stop_act_arr = ""
            
            if "pass" in stop.get("class"):
                stop_stops_here = False
            else:
                stop_plan_arr_tmp = wtt_tag.find('div', class_='arr')
                if stop_plan_arr_tmp is not None:
                    stop_plan_arr = formatTime(stop_plan_arr_tmp.text.replace("\u00bc", "15").replace("\u00bd", "30").replace("\u00be", "45").replace("pass", ""))
                if realtime_tag is not None:
                    stop_act_arr_tmp = realtime_tag.find('div', class_='arr')
                    if stop_act_arr_tmp is not None:
                        stop_act_arr = formatTime(stop_act_arr_tmp.text.replace("\u00bc", "15").replace("\u00bd", "30").replace("\u00be", "45").replace("N/R", ""))            

            try:
                stop_act_dep = realtime_tag.find('div', class_='dep').text
                stop_act_dep = formatTime(stop_act_dep.replace("\u00bc", "15").replace("\u00bd", "30").replace("\u00be", "45").replace("N/R", ""))
            except:
                stop_act_dep = ""

            try:
                stop_plan_dep = formatTime(wtt_tag.find('div', class_='dep').text.replace("\u00bc", "15").replace("\u00bd", "30").replace("\u00be", "45"))
            except:
                stop_plan_dep = ""

            
            stop_as_required = False
            if stop_act_dep == "(Q)":
                stop_act_dep = ""
                stop_as_required = True

            stop_is_delayed = False
            if (stop_act_dep == "Delay") or (stop_act_arr == "Delay"):
                stop_act_dep = ""
                stop_act_arr = ""
                stop_is_delayed = True

            stop_is_cancelled = False
            if (stop_act_dep == "Cancel") or (stop_act_arr == "Cancel"):
                stop_act_dep = ""
                stop_act_arr = ""
                is_cancelled = True

            stop_plan_arr = getUnixTime(stop_plan_arr)
            stop_plan_dep = getUnixTime(stop_plan_dep)
            stop_act_arr = getUnixTime(stop_act_arr)
            stop_act_dep = getUnixTime(stop_act_dep)

            dist_tag = stop.find('div', class_='distance')
            delay_tag = stop.find('div', class_='delay')
            path_tag = stop.find('div', class_='path')
            line_tag = stop.find('div', class_='line')

            delay = 0;
            if delay_tag is not None:
                if not delay_tag.text == "":
                    delay = int(delay_tag.text) * 60


            distance = 0.00
            if dist_tag is not None:
                if not dist_tag.text == "":
                    distance = float(dist_tag.text)
            
            stop_location_fullname = re.sub("\[.*?\]", "", stop_location.text).strip()
            stop_location_short = stop_location.text.replace(stop_location_fullname, "").strip().replace("[","").replace("]","")

            #if stop_location_short == station_name:
            #   after_this_station = True

            if stop_plan_dep == 0:
                if plan_dep == 0:
                    if stop_plan_arr > plan_arr:
                        after_this_station = True
                else:
                    if stop_plan_arr > plan_dep:
                        after_this_station = True
            else:
                if plan_dep == 0:
                    if stop_plan_dep > plan_arr:
                        after_this_station = True
                else:
                    if stop_plan_dep > plan_dep:
                        after_this_station = True
                
            stop_datum = {
                "distance":distance,
                "location":stop_location_fullname,
                "location_short":stop_location_short,
                "plan_arr":stop_plan_arr,
                "plan_dep":stop_plan_dep,
                "act_arr":stop_act_arr,
                "act_dep":stop_act_dep,
                "delay":delay,
                "platform":"" if stop_platform is None else stop_platform,
                "path":path_tag.text if path_tag is not None else "",
                "line":line_tag.text if line_tag is not None else "",
                "is_station":False if stop_location_short == "" else True,
                "stops_here":stop_stops_here,
                "after_this_station":after_this_station if not stop_location_short == station_name else False
            }
            stops.append(stop_datum)

    destination = service.find('div', class_="d").text
    if "Terminating short here" in destination:
        destination = station_fullname

    origin = service.find('div', class_="o").text
    if "Starting short here" in origin:
        origin = station_fullname
    cars = service.find('div', class_="cars").text
    operator = service.find('div', class_="toc").text
    stp = service.find('div', class_="stp").text
    platform = service.find('div', class_="platform").text

    ''' # disabled - designed for old code - needs updating to accommodate changes
    at_platform = False
    arriving = False
    if plan_dep == "At platform":
        at_platform = True
    if plan_dep == "Arriving":
        arriving = True
    '''
    
    if train_id == "":
        train_id = tid.text

    service_datum = {
        "train_uid": train_uid,
        "train_id": train_id,
        "stp": stp,
        "origin": origin if (not "Starts here" in origin) else station_fullname,
        "destination": (destination if (not "Terminates here" in destination) else station_fullname).removesuffix("At platform").removesuffix("Arriving"),
        "plan_arr": plan_arr,
        "act_arr": act_arr,
        "plan_dep": plan_dep,
        "act_dep": plan_dep,
        "platform": platform,
        #"at_platform": at_platform,
        #"arriving": arriving,
        "cars": cars,
        "is_bus": is_bus,
        "operator": operator,
        "identities": identities,
        "stops": stops,
        "stops_here": "pass" not in service.get("class"),
        "is_cancelled": is_cancelled
    }

    
    data.append(service_datum)
    #print(service_datum) # debug to print services one by one - doesn't produce valid json

json_data = json.dumps(data, indent=4)


print(json_data)

