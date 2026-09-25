import json
from flask import redirect, jsonify
from finalfrsproject import sqlCommands

def get_handler(request):
    term = request.args.get('term')
    #results = get_autocomplete_vehicles(term)
    results = sqlCommands.get_all_vehicles_details_for_autocomplete(term)
    if not results or results.get('Status') == "Fail":        
        return redirect(request.url)
        
    results = results.get("Details")
    if len(results) > 0:
        print('rows returned: ', len(results))
        formatted_vehicles = []
        for result in results:
            formatted_vehicles.append({
                'id': result[0], 
                'plate': result[1]
            })
        print("vehicle auto complete results: ", results);
        return jsonify(formatted_vehicles)
