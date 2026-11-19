+++
title = {{ replace .File.ContentBaseName "-" " " | title | jsonify }}
date = {{ .Date }}
slug = {{ .File.ContentBaseName | urlize | jsonify }}
draft = true
tags = []
# series = ["Series name"]
summary = ""
+++
