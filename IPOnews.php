<?php
#Initialization
include("./W3SLibs/LIB_http.php");
include("./W3SLibs/LIB_parse.php");
include("./W3SLibs/LIB_mysql.php");
#File for storing daily updates
$filepath = "./updates.txt";
$fp = fopen($filepath, "w");
#Arrays to store extracted information
$Wd_IPO_array = array();
$Rp_IPO_array = array();
$Up_IPO_array = array();
$Tsxr_array = array();
$Tsxd_array = array();
$Tsvr_array = array();
$Tsvd_array = array();

#Endpoints containing listing data
//NASDAQ endpoints
$nasdaqWD = "https://www.nasdaq.com/markets/ipos/activity.aspx?tab=withdrawn";
$nasdaqUP = "https://www.nasdaq.com/markets/ipos/activity.aspx?tab=upcoming";
$nasdaqRP = "https://www.nasdaq.com/markets/ipos/activity.aspx?tab=pricings";
//TSX/TSXV endpoints
$TSXhost = "www.tsx.com";
$TSVrecent = "/json/company-directory/recent/tsxv";
$TSXrecent = "/json/company-directory/recent/tsx";
$TSXdelist = "/json/company-directory/delisted/tsx";
$TSVdelist = "/json/company-directory/delisted/tsxv";

#Database table structures
//NASDAQ(cname, market, price, adate)
//TSXV(cname, adate, symbol)

function getWebpage($target){
	// Initialize session and set URL.
	$ch = curl_init();
	curl_setopt($ch, CURLOPT_URL, $target);

	// Set so curl_exec returns the result instead of outputting it.
	curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
	curl_setopt($ch, CURLOPT_USERAGENT, "curl/7.37.0");
	curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
	// Get the response and close the channel.
	$response = curl_exec($ch);

	//echo curl_getinfo($ch) . '\n';
	//echo curl_errno($ch) . '\n';
	//echo curl_error($ch) . '\n';

	curl_close($ch);
	return $response;
}

function getCompanyName($rowData) {
	$compName = return_between($rowData, ">", "</a>", EXCL);
    $compName = remove($compName, "<a", ">");
	return $compName;	
}
function getValue($rowData) {
    return return_between($rowData, "<td>", "</td>", EXCL);
}

function parseNDWD($webpage) { //parse nasdaq withdraw page

    if (stristr($webpage, "There is no data for this month, please select a prior month.")) {
		return null;
	}

	$out_array = array();
    $parsedTable = return_between($webpage, "<table", "</table>", INCL);
    $parsedRow = parse_array($parsedTable, "<tr", "</tr>");
    for ($idx=1; $idx<count($parsedRow); $idx++) {
        $parsedRD = parse_array($parsedRow[$idx], "<td", "</td>");
        $out_array[$idx-1]['cname'] =  getCompanyName($parsedRD[0]);
        $out_array[$idx-1]['market'] = null;
		$out_array[$idx-1]['price'] = null;
		$out_array[$idx-1]['adate'] = getValue($parsedRD[7]);
    }
    return $out_array;
}

function parseNDRP($webpage) { //parse nasdaq recently priced page

    if (stristr($webpage, "There is no data for this month, please select a prior month.")) {
        return null;
    }

	$out_array = array();
    $parsedTable = return_between($webpage, "<table", "</table>", INCL);
    $parsedRow = parse_array($parsedTable, "<tr", "</tr>");
    for ($idx=1; $idx<count($parsedRow); $idx++) {
        $parsedRD = parse_array($parsedRow[$idx], "<td", "</td>");
        $out_array[$idx-1]['cname'] =  getCompanyName($parsedRD[0]);
        $out_array[$idx-1]['market'] = getValue($parsedRD[2]);
        $out_array[$idx-1]['price'] = getValue($parsedRD[3]);
		$out_array[$idx-1]['adate'] = getValue($parsedRD[6]);
	}
	return $out_array;
}

function parseNDUP($webpage) { //parse nasdaq upcoming ipo page
    $out_array = array();
    $parsedTable = return_between($webpage, "<table", "</table>", INCL);
    $parsedRow = parse_array($parsedTable, "<tr", "</tr>");
    for ($idx=1; $idx<count($parsedRow); $idx++) {
        $parsedRD = parse_array($parsedRow[$idx], "<td", "</td>");

        if (stristr(getValue($parsedRD[3]), "TBA")){
			break;
		}

		$out_array[$idx-1]['cname'] =  getCompanyName($parsedRD[0]);
        $out_array[$idx-1]['market'] = getValue($parsedRD[2]);
        $out_array[$idx-1]['price'] = getValue($parsedRD[3]);
        $out_array[$idx-1]['adate'] = getValue($parsedRD[6]);
    }
    return $out_array;
}

function parseTSXV($webpage) {  //parse all Tsx/v pages
	$out_array = array();
	$pageData = return_between($webpage, "[", "]", EXCL);
	$parsedRow = parse_array($pageData, "{", "}");
	for ($idx=0; $idx<count($parsedRow); $idx++) {
		$out_array[$idx]['cname'] = str_replace("\"", "",return_between($parsedRow[$idx], "\"name\":", ",", EXCL));
		$out_array[$idx]['adate'] = date('Y/m/d',return_between($parsedRow[$idx], "\"date\":", ",", EXCL));
		$out_array[$idx]['symbol'] = str_replace("\"", "", return_between($parsedRow[$idx], "\"symbol\":", "}", EXCL));
	}
	return $out_array;
}

function NotInNDdb($company) {// Pass in array of elements i.e. $Wd_IPO_array[x]
	$baseQuery = "select * from nasdaq where cname=\"";
	$nasdaqDB = exe_sql(DATABASE, $baseQuery.$company['cname']."\"");
	if(count($nasdaqDB) > 0){
    	//echo "Already in DB\n";
		return false;
	} else {
    	//echo "New entry added\n";
    	insert(DATABASE,$table="nasdaq", $company);
		return true;
	}
}

function NotInTSdb($company) {
	$baseQuery = "select * from tsxv where cname=\"";
    $tsxvDB = exe_sql(DATABASE, $baseQuery.$company['cname']."\"");
    if(count($tsxvDB) > 0){
        //echo "Already in DB\n";
		return false;
    } else {
        //echo "New entry added\n";
        insert(DATABASE,$table="tsxv", $company);
		return true;
    }
}

function CheckForUpdates($in_array, $db_name) {
	global $fp;

	if ($in_array == NULL) {
		return;
	}
	for($idx=0; $idx<count($in_array); $idx++) {
		switch ($db_name) {
			case "NSDQ":
				if (NotInNDdb($in_array[$idx])) {
					//Write to file to be read in python
					$wdata = $in_array[$idx]['cname']."\t".$in_array[$idx]['market']."\t".$in_array[$idx]['price']."\t".$in_array[$idx]['adate']."\n";
					fwrite($fp,$wdata);
				}
				continue;
			case "TSXV":
                if (NotInTSdb($in_array[$idx])) {
                    //Write to file to be read in python
					$wdata = $in_array[$idx]['cname']."\t".$in_array[$idx]['symbol']."\t".$in_array[$idx]['adate']."\n";
                    fwrite($fp,$wdata); 
                }
				continue;
		}
	}	
}

echo "Parsing webpages....";

$Wd_IPO_array = parseNDWD(getWebpage($nasdaqWD));
$Rp_IPO_array = parseNDRP(getWebpage($nasdaqRP));
$Up_IPO_array = parseNDUP(getWebpage($nasdaqUP));
$Tsxr_array = parseTSXV(getWebpage($TSXhost.$TSXrecent));
$Tsxd_array = parseTSXV(getWebpage($TSXhost.$TSXdelist));
$Tsvr_array = parseTSXV(getWebpage($TSXhost.$TSVrecent));
$Tsvd_array = parseTSXV(getWebpage($TSXhost.$TSVdelist));

echo "Done\n";
echo "Checking for updates....";

// Check each array for updates and prepare updates.txt
fwrite($fp, "NASDAQ Withdraw:\n\n");
CheckForUpdates($Wd_IPO_array,"NSDQ");
fwrite($fp, "\nNASDAQ Recently Priced:\n\n");
CheckForUpdates($Rp_IPO_array,"NSDQ");
fwrite($fp, "\nNASDAQ Upcoming:\n\n");
CheckForUpdates($Up_IPO_array,"NSDQ");
fwrite($fp, "\nTSX recent:\n\n");
CheckForUpdates($Tsxr_array,"TSXV");
fwrite($fp, "\nTSX delisted:\n\n");
CheckForUpdates($Tsxd_array,"TSXV");
fwrite($fp, "\nTSV recent:\n\n");
CheckForUpdates($Tsvr_array,"TSXV");
fwrite($fp, "\nTSV delisted:\n\n");
CheckForUpdates($Tsvd_array,"TSXV");
echo "Done\n";

fclose($fp);
?>
