#pragma once
#include <drogon/drogon.h>
namespace mirage::http
{
using Callback = std::function<void(const drogon::HttpResponsePtr &)>;
void reply(const Callback &, drogon::HttpStatusCode, const Json::Value &);
void error(const Callback &, drogon::HttpStatusCode, const char *);
bool field(const Json::Value &, const char *, size_t, size_t);
bool email(const Json::Value &);
bool json(const drogon::HttpRequestPtr &, Json::Value &, const Callback &);
bool bearer(const drogon::HttpRequestPtr &, std::string &, const Callback &);
bool loginAllowed(const drogon::HttpRequestPtr &, const Callback &);
} // namespace mirage::http
