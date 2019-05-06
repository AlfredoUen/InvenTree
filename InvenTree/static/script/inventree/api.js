var jQuery = window.$;

// using jQuery
function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie != '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) == (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function inventreeGet(url, filters={}, options={}) {
    return $.ajax({
        url: url,
        type: 'GET',
        data: filters,
        dataType: 'json',
        contentType: 'application/json',
        success: function(response) {
            console.log('Success GET data at ' + url);
            if (options.success) {
                options.success(response);
            }
        },
        error: function(xhr, ajaxOptions, thrownError) {
            console.error('Error on GET at ' + url);
            console.error(thrownError);
            if (options.error) {
                options.error({
                    error: thrownError
                });
            }
        }
    });
}

function inventreeFileUpload(url, file, data={}, options={}) {
    /* Upload a file via AJAX using the FormData approach.
     * 
     * Note that the following AJAX parameters are required for FormData upload
     * 
     * processData: false
     * contentType: false
     */

    // CSRF cookie token
    var csrftoken = getCookie('csrftoken');
    
    var data = new FormData();
    
    data.append('file', file);

    return $.ajax({
        beforeSend: function(xhr, settings) {
            xhr.setRequestHeader('X-CSRFToken', csrftoken);
        },
        url: url,
        method: 'POST',
        data: data,
        processData: false,
        contentType: false,
        success: function(data, status, xhr) {
            console.log('Uploaded file - ' + file.name);

            if (options.success) {
                options.success(data, status, xhr);
            }
        },
        error: function(xhr, status, error) {
            console.log('Error uploading file: ' + status);

            if (options.error) {
                options.error(xhr, status, error);
            }
        }
    });
}

function inventreePut(url, data={}, options={}) {

    var method = options.method || 'PUT';

    // Middleware token required for data update
    //var csrftoken = jQuery("[name=csrfmiddlewaretoken]").val();
    var csrftoken = getCookie('csrftoken');

    return $.ajax({
        beforeSend: function(xhr, settings) {
            xhr.setRequestHeader('X-CSRFToken', csrftoken);
        },
        url: url,
        type: method,
        data: JSON.stringify(data),
        dataType: 'json',
        contentType: 'application/json',
        success: function(response, status) {
            console.log(method + ' - ' + url + ' : result = ' + status);
            if (options.success) {
                options.success(response, status);
            }
            if (options.reloadOnSuccess) {
                location.reload();
            }
        },
        error: function(xhr, ajaxOptions, thrownError) {
            console.error('Error on UPDATE to ' + url);
            console.error(thrownError);
            if (options.error) {
                options.error(xhr, ajaxOptions, thrownError);
            }
        }
    });
}

// Return list of parts with optional filters
function getParts(filters={}, options={}) {
    return inventreeGet('/api/part/', filters, options);
}

// Return list of part categories with optional filters
function getPartCategories(filters={}, options={}) {
    return inventreeGet('/api/part/category/', filters, options);
}

function getCompanies(filters={}, options={}) {
    return inventreeGet('/api/company/', filters, options);
}

function updateStockItem(pk, data, final=false) {
    return inventreePut('/api/stock/' + pk + '/', data, final);
}

function updatePart(pk, data, final=false) {
    return inventreePut('/api/part/' + pk + '/', data, final);
}