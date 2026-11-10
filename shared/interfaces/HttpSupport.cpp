#include "HttpSupport.h"
#include <chrono>
#include <mutex>
#include <unordered_map>
using namespace drogon;
namespace mirage::http
{
void reply(const Callback &callback, HttpStatusCode status, const Json::Value &body)
{
    auto response = HttpResponse::newHttpJsonResponse(body);
    response->setStatusCode(status);
    response->addHeader("Cache-Control", "no-store");
    callback(response);
}

void error(const Callback &callback, HttpStatusCode status, const char *code)
{
    Json::Value body;
    body["error"] = code;
    reply(callback, status, body);
}

bool field(const Json::Value &body, const char *key, size_t min, size_t max)
{
    const auto &value = body[key];
    return value.isString() && value.asString().size() >= min && value.asString().size() <= max &&
           value.asString().find('\0') == std::string::npos;
}

bool email(const Json::Value &body)
{
    if (!field(body, "email", 3, 254))
        return false;
    const auto value = body["email"].asString();
    const auto at = value.find('@');
    return at != std::string::npos && at > 0 && at + 1 < value.size() &&
           value.find_first_of(" \r\n\t") == std::string::npos;
}

bool json(const HttpRequestPtr &req, Json::Value &body, const Callback &callback)
{
    if (req->body().size() > 16384)
    {
        error(callback, k413RequestEntityTooLarge, "body_too_large");
        return false;
    }
    auto value = req->getJsonObject();
    if (!value || !value->isObject())
    {
        error(callback, k400BadRequest, "invalid_json");
        return false;
    }
    body = *value;
    return true;
}

bool bearer(const HttpRequestPtr &req, std::string &token, const Callback &callback)
{
    token = req->getHeader("authorization");
    if (token.size() <= 7 || token.size() > 8192 || token.compare(0, 7, "Bearer ") != 0 ||
        token.find_first_of("\r\n\t") != std::string::npos)
    {
        error(callback, k401Unauthorized, "bearer_token_required");
        return false;
    }
    return true;
}

// shortcut: per-process/IP limit; move to shared storage before using replicas.
bool loginAllowed(const HttpRequestPtr &req, const Callback &callback)
{
    using Clock = std::chrono::steady_clock;
    struct Window
    {
        Clock::time_point start;
        unsigned count;
    };
    static std::mutex mutex;
    static std::unordered_map<std::string, Window> windows;
    std::lock_guard<std::mutex> lock(mutex);
    const auto now = Clock::now();
    for (auto it = windows.begin(); it != windows.end();)
    {
        if (now - it->second.start >= std::chrono::seconds(120))
            it = windows.erase(it);
        else
            ++it;
    }
    const auto ip = req->peerAddr().toIp();
    auto it = windows.find(ip);
    if (it == windows.end())
    {
        if (windows.size() >= 10000)
        {
            error(callback, k429TooManyRequests, "too_many_attempts");
            return false;
        }
        it = windows.emplace(ip, Window{now, 0}).first;
    }
    // Count all attempts, including successful ones, to bound concurrent requests.
    if (it->second.count >= 5)
    {
        error(callback, k429TooManyRequests, "too_many_attempts");
        return false;
    }
    ++it->second.count;
    return true;
}

} // namespace mirage::http
