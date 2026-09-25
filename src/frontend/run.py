from finalfrsproject import app


if __name__ == '__main__':
    #app.run(host='0.0.0.0', port=2204, ssl_context=('/home/vajr28/visitor-vehicle/Visitor-Vehicle-New-Containers/src/frontend/cert.pem', '/home/vajr28/visitor-vehicle/Visitor-Vehicle-New-Containers/src/frontend/key.pem'), threaded=True, debug=True)
    app.run(host='0.0.0.0', port=2204, ssl_context=('cert.pem', 'key-new.pem'), threaded=True, debug=True)
#cv2.destroyAllWindows()