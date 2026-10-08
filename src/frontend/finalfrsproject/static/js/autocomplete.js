$(function() {
    var root = window.APP_ROOT || "";
    $("#searchInput").autocomplete({
        source: function(request, response) {
            $.ajax({
                url: root + "/autocomplete",
                data: { term: request.term },
                success: function(data) {
                    response(data.map(function(item) {
                        return {
                            label: item.plate, // Displayed in the autocomplete dropdown
                            value: item.plate, // Value to be filled in the input field
                            id: item.id // Additional data (vehicle_id)
                        };
                    }));
                }
            });
        },
        minLength: 2,
        select: function(event, ui) {
            // Redirect to the vehicle_details route with the selected vehicle_id
            window.location.href = root + "/vehicle/" + ui.item.id;
        }
    });
});
