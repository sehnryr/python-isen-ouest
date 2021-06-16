#!/usr/bin/env python
# -*- coding: utf-8 -*-

import regex
import requests
import xlrd
from requests_html import HTMLSession, HTMLResponse
from typing import Any, Dict, List


class Client:
	def __init__(self) -> None:
		self.uid: int = None
		self.gid: int = None  # dunno what's its use
		self.first_name: str = None
		self.last_name: str = None
		self.mail: str = None
		self.username: str = None

		self.trombinoscope: Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]] = dict()

		self.session: HTMLSession = HTMLSession()

	def __repr__(self) -> str:
		return "<WebISEN name={} uid={}>".format(
			f'"{self.first_name} {self.last_name}"' if self.first_name != None else "None",
			self.uid if self.uid != None else "None",
		)

	def login(self, username, password) -> HTMLResponse:
		response: HTMLResponse = self.session.get(url="https://auth.isen-ouest.fr/cas/login")
		execution: str = (
			t[0].attrs["value"]
			if len(t := response.html.xpath("//input[@name='execution']")) == 1
			else None
		)  # secret execution string

		if execution == None:
			raise ValueError("Could not find the execution string.")

		request = self.session.post(
			url="https://auth.isen-ouest.fr/cas/login",
			data={
				"username": username,
				"password": password,
				"execution": execution,
				"_eventId": "submit",
			},
		)

		if request.status_code != 200:
			raise ConnectionError(f"Request returned error code : {request.status_code}")

		user_data: dict = dict(
			map(
				lambda elem: regex.search(
					r"<span>([^<]+)<\/span>(?:\s|.)+?<span>\[([^<]+)\]<\/span>", elem.html
				).groups(),
				request.html.xpath("//tr[@class='mdc-data-table__row']"),
			)
		)

		self.uid = user_data["uidNumber"]
		self.gid = user_data["gidNumber"]
		self.first_name = user_data["FirstName"]
		self.last_name = user_data["LastName"]
		self.mail = user_data["Mail"]
		self.username = user_data["Login"]

		return request

	def get_trombinoscope(self) -> Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]]:

		self.session.get(url="https://web.isen-ouest.fr/trombino/")  # obtaining the cookie

		headers = {"Content-Type": "application/x-www-form-urlencoded"}

		list_cycles_url: str = "https://web.isen-ouest.fr/trombino/fonctions/ajax/lister_cycles.php"
		list_years_url: str = "https://web.isen-ouest.fr/trombino/fonctions/ajax/lister_annees.php"
		list_groups_url: str = "https://web.isen-ouest.fr/trombino/fonctions/ajax/lister_groupes.php"
		list_students_url: str = "https://web.isen-ouest.fr/trombino/fonctions/ajax/lister_etudiants.php"

		find_values = lambda url, data=None: filter(
			lambda value: value != "-1",
			regex.findall(
				r'<option.+?value="([^"]*)".*?>',
				self.session.post(url=url, headers=headers, data=data).html.html,
			),
		)

		for cycle in find_values(url=list_cycles_url):
			self.trombinoscope[cycle] = dict()
			for year in find_values(url=list_years_url, data=f"choix_cycle={cycle}"):
				self.trombinoscope[cycle][year] = dict()
				for group in find_values(
					url=list_groups_url, data=f"choix_cycle={cycle}&choix_annee={year}"
				):
					xls = regex.search(
						r'"([^"]+\.xls)"',
						self.session.post(
							url=list_students_url, headers=headers, data=f"choix_groupe={group}"
						).html.html,
					)
					if xls == None:
						continue
					xls_url: str = xls.group(1)
					xls_data = requests.get(url=xls_url).content

					try:
						book = xlrd.open_workbook(file_contents=xls_data)
					except:
						continue
					if book.nsheets != 1:
						continue

					self.trombinoscope[cycle][year][group] = list()

					sh = book.sheet_by_index(0)
					for rx in range(2, sh.nrows):
						row: List[Any] = sh.row(rx)
						row = list(map(lambda cell: cell.value if cell.value != "" else None, row))
						self.trombinoscope[cycle][year][group].append(
							{
								"uid": int(row[0]) if row[0] != None else None,
								"last_name": row[1],
								"first_name": row[2],
								"phone": row[3],
								"mail": row[4],
							}
						)

		return self.trombinoscope