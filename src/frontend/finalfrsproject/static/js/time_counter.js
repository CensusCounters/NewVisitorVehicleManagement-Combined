		var active;		
		
		function initTimeCounters() {
	        active = false;

	        var body = document.getElementById('body');
	        body.onkeypress = function(e){
	        	active = true;
	        }
	        body.onclick = function(e){
	        	active = true;
	        }
	          	        
	        checkActivity(1800000, 600000, 0); 			
		}

    	function checkActivity(timeout, interval, elapsed) {
    	    if(active) {
    	        elapsed = 0;
    	        active = false;
    	    }
    	    if(elapsed < timeout) {
    	        elapsed += interval;
    	        setTimeout(function() {
    	        	checkActivity(timeout, interval, elapsed);
    	        }, interval);
    	    } else {
    	        window.location = 'login'; 
    	    }
    	}