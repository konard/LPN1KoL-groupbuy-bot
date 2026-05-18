<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class StatsAuth
{
    public function handle(Request $request, Closure $next): Response|RedirectResponse
    {
        if (! $request->session()->get('visitor_stats_authorized')) {
            return redirect()->route('stats.login');
        }

        return $next($request);
    }
}
