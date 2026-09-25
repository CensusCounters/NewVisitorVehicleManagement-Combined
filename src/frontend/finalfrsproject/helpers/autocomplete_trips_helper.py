import json
from flask import redirect, jsonify
from finalfrsproject import sqlCommands

def get_handler(request):
    term = request.args.get('term')
    print("term: ", term)
    #results = get_autocomplete_trips(term)
    #print("result term: ", results)
    result = sqlCommands.get_all_trips_for_autocomplete(term)
    print("result: ", result)

    if not result or result.get('Status') == "Fail":        
        return redirect(request.url)
    
    results = result.get("Details")
    if len(results) > 0:
        print('rows returned: ', len(result))
        formatted_trips = []
        for result in results:
            formatted_trips.append({
                'id': result[0], 
                'vehicle_number_plate': result[1]
            })
        print("auto complete results: ", results);
        return jsonify(formatted_trips)