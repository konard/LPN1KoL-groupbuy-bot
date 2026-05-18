<?php

use Illuminate\Support\Facades\Schedule;

Schedule::command('api-records:fetch')->everyFiveMinutes();
