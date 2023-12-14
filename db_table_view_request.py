from sqlalchemy import create_engine, text
import pandas as pd
import os
import json
import requests
from datetime import datetime
import pytz
from pprint import pprint


def get_data_from_VF_single_vessel_positions(imo_list):
    single_vessel_positions_df = pd.DataFrame()
    print("Start of get_data_from_single_vessel_positions.............")
    print(f"input_list = {imo_list}")

    api_key = os.environ['VF_API_KEY']

    base_url = f"https://api.vesselfinder.com/vessels?userkey={api_key}"

    VF_ais_response = requests.get(f"{base_url}&imo={imo_list}")
    print(f"VF_ais_response.json() = {VF_ais_response.json()}")
    VF_ais_data = VF_ais_response.json()

    VF_ais_info = [entry["AIS"] for entry in VF_ais_data]
    single_vessel_positions_df = pd.DataFrame(VF_ais_info)
    print(f"single_vessel_positions_df = {single_vessel_positions_df}")
    single_vessel_positions_df.rename(
        columns={
            "MMSI": "mmsiNumber",
            "TIMESTAMP": "timeStamp",
            "LATITUDE": "latitudeDegrees",
            "LONGITUDE": "longitudeDegrees",
            "COURSE": "course",
            "SPEED": "speed",
            "HEADING": "heading",
            "IMO": "imoNumber",
            "CALLSIGN": "callSign",
        },
        inplace=True,
    )
    single_vessel_positions_df.drop(
        columns=[
            "A",
            "B",
            "C",
            "D",
            "ECA",
            "LOCODE",
            "SRC",
            "DRAUGHT",
            "NAVSTAT",
        ],
        inplace=True,
    )

    # print(VF_ais_info)
    pprint(single_vessel_positions_df)
    return single_vessel_positions_df


# get VDA from MPA API
def get_data_from_vessel_due_to_arrive_and_depart():
    print("Start of get_data_from_vessel_due_to_arrive_and_depart........")

    # Define your local time zone (UTC+9)
    local_timezone = pytz.timezone("Asia/Singapore")
    # Get the current date and time in UTC
    current_utc_datetime = datetime.now(pytz.utc)

    # Convert the current UTC time to your local time zone
    current_local_datetime = current_utc_datetime.astimezone(local_timezone)
    today_datetime = current_local_datetime.strftime("%Y-%m-%d %H:%M:%S")

    url_MPA_due_to_arrive = f"https://sg-mdh-api.mpa.gov.sg/v1/vessel/duetoarrive/date/{today_datetime}/hours/99"
    url_MPA_due_to_depart = f"https://sg-mdh-api.mpa.gov.sg/v1/vessel/duetodepart/date/{today_datetime}/hours/99"

    API_KEY_MPA = "QgCv2UvINPRfFqbbH3yVHRVVyO8Iv5CG"

    MPA_due_to_arrive_GET = requests.get(
        url_MPA_due_to_arrive, headers={"Apikey": API_KEY_MPA}
    )
    # Check the response
    if MPA_due_to_arrive_GET.status_code == 200:
        print(
            "db_table_view_request.py: get_data_from_vessel_due_to_arrive_and_depart(): Arrive Data retrieved successfully!"
        )
        # query and values
        dueToArrive_Data = json.loads(MPA_due_to_arrive_GET.text)
        arrive_df = pd.json_normalize(dueToArrive_Data)
    else:
        print("Failed to get vessel_due_to_arrive data")

    MPA_due_to_depart_GET = requests.get(
        url_MPA_due_to_depart, headers={"Apikey": API_KEY_MPA}
    )
    # Check the response
    if MPA_due_to_depart_GET.status_code == 200:
        print(
            "db_table_view_request.py: get_data_from_vessel_due_to_arrive_and_depart(): Depart Data retrieved successfully!"
        )
        # query and values
        dueToDepart_Data = json.loads(MPA_due_to_depart_GET.text)
        depart_df = pd.json_normalize(dueToDepart_Data)
    else:
        print("Failed to get vessel_due_to_depart data")

    merged_df = arrive_df.merge(depart_df, on="vesselParticulars.imoNumber", how="left")
    merged_df.drop(
        columns=[
            "vesselParticulars.vesselName_y",
            "vesselParticulars.vesselName_y",
            "vesselParticulars.flag_y",
            "vesselParticulars.callSign_y",
        ],
        inplace=True,
    )
    print(f"get_data_from_vessel_due_to_arrive_and_depart.merge_df = {merged_df}")
    return merged_df


def merge_arrivedepart_VF_df(
  filtered_arrive_depart_MPA_df, VF_Single_Vessel_Positions_df
):
  # Merge Declaration_df with filtered_df
  print(
      f"db_table_view_request.py filtered_arrive_depart_MPA_df = {filtered_arrive_depart_MPA_df}"
  )
  # filtered_arrive_depart_MPA_df.to_excel(
  #     "table view filtered_arrive_depart_MPA_df.xlsx"
  # )
  print(
      f"db_table_view_request.py VF_Single_Vessel_Positions_df = {VF_Single_Vessel_Positions_df}"
  )
  # VF_Single_Vessel_Positions_df.to_excel(
  #     "table view VF_Single_Vessel_Positions_df.xlsx"
  # )

  # rename column name from vesselParticulars.imoNumber to imoNumber for filtered_arrive_depart_MPA_df
  filtered_arrive_depart_MPA_df.rename(
      columns={
          "vesselParticulars.imoNumber": "imoNumber",
          "duetoArriveTime": "ETA - MPA",
          "dueToDepart": "ETD - MPA",
          "vesselParticulars.flag_x": "flag",
      },
      inplace=True,
  )
  filtered_arrive_depart_MPA_df["imoNumber"] = filtered_arrive_depart_MPA_df[
      "imoNumber"
  ].astype(int)
  VF_Single_Vessel_Positions_df["imoNumber"] = VF_Single_Vessel_Positions_df[
      "imoNumber"
  ].astype(int)
  VF_Single_Vessel_Positions_df.rename(
      columns={
          "ETA": "ETA - VesselFinder",
      },
      inplace=True,
  )

  Final_df = VF_Single_Vessel_Positions_df.merge(
      filtered_arrive_depart_MPA_df,
      how="outer",
      on="imoNumber",
  )
  print(f"db_table_view_request.py Final df = {Final_df}")
  # Reorder columns in place
  desired_column_order = [
      "imoNumber",
      "NAME",
      "DESTINATION",
      "ETA - VesselFinder",
      "ETA - MPA",
      "ETD - MPA",
      "callSign",
      "flag",
      "speed",
      "timeStamp",
  ]
  Final_df = Final_df[desired_column_order]
  print(f"Final_df = {Final_df}")
  filtered_df = Final_df
  timestamp_str = filtered_df["ETA - VesselFinder"]
  timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S UTC")
  # Add 8 hours to the timestamp
  new_timestamp = timestamp + timedelta(hours=8)
  print(
      f"db_table_view_request.py: get_data_from_VF_vessels(imo_list): New timestamp = {new_timestamp}"
  )
  # Format the new timestamp back into the desired string format
  new_timestamp_str = new_timestamp.strftime("%Y-%m-%d %H:%M:%S")
  print(
      f"db_table_view_request.py: get_data_from_VF_vessels(imo_list): new_timestamp_str = {new_timestamp_str}"
  )
  filtered_df["ETA - VesselFinder"] = new_timestamp_str
  with open("templates/Banner table.html", "r") as file:
      menu_banner_html = file.read()

  if filtered_df.empty:
      print(f"Empty table_df................")
      current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
      for f in os.listdir("templates/"):
          # print(f)
          if "mytable.html" in f:
              print(f"*mytable.html file to be removed = {f}")
              os.remove(f"templates/{f}")
      return 1  # render_template("table_view.html")
  else:
      for f in os.listdir("templates/"):
          # print(f)
          if "mytable.html" in f:
              print(f"*mytable.html file to be removed = {f}")
              os.remove(f"templates/{f}")
      current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")
      newHTML = rf"templates/{current_datetime}mytable.html"
      filtered_df.index = filtered_df.index + 1
      filtered_df.to_html(newHTML)
      with open(newHTML, "r") as file:
          html_content = file.read()
      # Add the menu banner HTML code to the beginning of the file
      html_content = menu_banner_html + html_content

      # Try new method
      html_content = html_content.replace(
          f'<table border="1" class="dataframe">',
          f'<table id="example" class="table table-striped table-bordered">',
      )

      html_content = html_content.replace(
          f"<thead>",
          f'<thead class="table-dark">',
      )
      html_content = html_content.replace(
          f"</table>",
          f'</table></div></div></div></div><script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js" integrity="sha384-ka7Sk0Gln4gmtz2MlQnikT1wXgYsOg+OMhuP+IlRH9sENBO0LRn5q+8nbTov4+1p" crossorigin="anonymous"></script><script src="/static/js/bootstrap.bundle.min.js"></script><script src="/static/js/jquery-3.6.0.min.js"></script><script src="/static/js/datatables.min.js"></script><script src="/static/js/pdfmake.min.js"></script><script src="/static/js/vfs_fonts.js"></script><script src="/static/js/custom.js"></script></body></html>',
      )

      # Write the modified HTML content back to the file
      with open(newHTML, "w") as file:
          file.write(html_content)
      print("it has reached here ===================")
      newHTMLrender = f"{current_datetime}mytable.html"
      return newHTMLrender