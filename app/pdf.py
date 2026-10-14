from pypdf import PdfReader, PdfWriter, errors

def get_pdf(html, options=None, output: PdfWriter | None = None):
    return
	# html = scrub_urls(html)
	# html, options = prepare_options(html, options)

	# options.update({"disable-javascript": "", "disable-local-file-access": ""})

	# filedata = ""
	# if Version(get_wkhtmltopdf_version()) > Version("0.12.3"):
	# 	options.update({"disable-smart-shrinking": ""})

	# try:
	# 	# Set filename property to false, so no file is actually created
	# 	filedata = pdfkit.from_string(html, options=options or {}, verbose=True)

	# 	# create in-memory binary streams from filedata and create a PdfReader object
	# 	reader = PdfReader(io.BytesIO(filedata))
	# except OSError as e:
	# 	if any([error in str(e) for error in PDF_CONTENT_ERRORS]):
	# 		if not filedata:
	# 			print(html, options)
	# 			frappe.throw(_("PDF generation failed because of broken image links"))

	# 		# allow pdfs with missing images if file got created
	# 		if output:
	# 			output.append_pages_from_reader(reader)
	# 	else:
	# 		raise
	# finally:
	# 	cleanup(options)

	# if "password" in options:
	# 	password = options["password"]

	# if output:
	# 	output.append_pages_from_reader(reader)
	# 	return output

	# writer = PdfWriter()
	# writer.append_pages_from_reader(reader)

	# if "password" in options:
	# 	writer.encrypt(password)

	# filedata = get_file_data_from_writer(writer)

	# return filedata